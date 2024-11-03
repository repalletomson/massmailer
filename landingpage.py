import streamlit as st 
from pymongo import MongoClient
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date
import pandas as pd
import matplotlib.pyplot as plt
# MongoDB Connection
client = MongoClient('mongodb://localhost:27017/email')
db = client['mass_mailer']
users_collection = db['users']
mails_collection = db['mails']
groups_collection = db['groups']
email_groups = db["email_groups"]
csv_records = db["csv_records"]  # Collection for CSV records
templates_collection = db["templates"]  # Collection for email templates

# Authentication Functions
def register_user(email, password):
    if users_collection.find_one({"email": email}):
        st.error("User already exists!")
    else:
        users_collection.insert_one({"email": email, "password": password})
        st.success("User registered successfully!")

def authenticate_user(email, password):
    user = users_collection.find_one({"email": email, "password": password})
    return user is not None
# Mail Logging and Stats Functions
def log_mail_activity(status, platform, recipients):
    mails_collection.insert_one({
        "status": status,
        "platform": platform,
        "timestamp": datetime.now(),
        "recipients": recipients  # Log recipients
    })

def get_mail_stats(platform=None):
    today = date.today()
    today = datetime.combine(today, datetime.min.time())
    
    # Base query for today
    query_today = {"timestamp": {"$gte": today}}
    # Base query for total counts
    query_all = {}

    # Add platform to the query if specified
    if platform:
        query_today["platform"] = platform
        query_all["platform"] = platform

    # Platform-specific counts
    mails_today = mails_collection.count_documents(query_today)
    total_mails = mails_collection.count_documents(query_all)
    sent_mails = mails_collection.count_documents({**query_all, "status": "sent"})
    failed_mails = mails_collection.count_documents({**query_all, "status": "failed"})
    spam_mails = mails_collection.count_documents({**query_all, "status": "spam"})

    return {
        "today": mails_today,
        "total": total_mails,
        "sent": sent_mails,
        "failed": failed_mails,
        "spam": spam_mails
    }

def get_daily_email_counts(platform=None):
    today = date.today()
    query = {"timestamp": {"$gte": datetime.combine(today, datetime.min.time())}}
    
    # Filter by platform if specified
    if platform:
        query["platform"] = platform

    mails = mails_collection.find(query)
    daily_counts = {}

    for mail in mails:
        date_key = mail['timestamp'].date()
        if date_key not in daily_counts:
            daily_counts[date_key] = 0
        daily_counts[date_key] += 1

    return daily_counts

# Email Sending Functions

def send_email_smtp(subject, body, recipients, smtp_info):
    try:
        # Unpack SMTP info
        smtp_server, smtp_port, sender_email, sender_password = smtp_info
        
        # Set up the SMTP server connection
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Secure the connection
        server.login(sender_email, sender_password)  # Login

        # Create the email message
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = ", ".join(recipients)
        message['Subject'] = subject
        message.attach(MIMEText(body, "plain"))  # Change to "html" if sending HTML emails

        # Send the email
        server.sendmail(sender_email, recipients, message.as_string())
        server.quit()
        
        # Streamlit success message
        st.success(f"Email sent successfully via {smtp_info[0]}!")
        
        # Log email as "sent"
        log_mail_activity("sent", smtp_info[0], recipients)
        
    except Exception as e:
        # Streamlit error message
        st.error(f"An error occurred: {e}")
        
        # Log email as "failed"
        log_mail_activity("failed", smtp_info[0], recipients)

# Function to create a group
def create_group(group_name, emails, user_id):
    email_groups.insert_one({
        "group_name": group_name,
        "emails": emails,
        "created_by": user_id,
        "last_sent": None
    })

# Group Management Functions
def get_user_groups(user_id, search_term=None):
    query = {"created_by": user_id}
    if search_term:
        query["group_name"] = {"$regex": search_term, "$options": "i"}  # Case-insensitive search
    return list(email_groups.find(query))

def save_group(group_name, recipients):
    if groups_collection.find_one({"group_name": group_name}):
        st.error("Group name already exists!")
    else:
        groups_collection.insert_one({"group_name": group_name, "recipients": recipients})
        st.success(f"Group '{group_name}' saved successfully!")

def get_groups():
    groups = email_groups.find()
    return {group['group_name']: group['emails'] for group in groups}
def update_group(group_id, group_name, emails):
    try:
        email_groups.update_one({"_id": group_id}, {"$set": {"group_name": group_name, "recipients": emails}})
        st.success(f"Group '{group_name}' updated successfully!")
    except Exception as e:
        st.error(f"Error updating group: {e}")
# CSV Handling Functions
def extract_emails_from_csv(file):
    df = pd.read_csv(file)
    emails = df['Email'].dropna().astype(str).tolist()    
    return emails

def store_csv_record(file_name, emails):
    csv_records.insert_one({
        "file_name": file_name,
        "emails": emails,
        "created_at": datetime.utcnow()
    })

def get_csv_records():
    return list(csv_records.find())


def delete_csv_record(file_name):
    csv_records.delete_one({"file_name": file_name})
def create_template(name, subject, body):
    templates_collection.insert_one({
        "name": name,
        "subject": subject,
        "body": body,
        "created_at": datetime.utcnow()
    })

def get_templates():
    return list(templates_collection.find())

def update_template(template_id, name, subject, body):
    templates_collection.update_one({"_id": template_id}, {"$set": {"name": name, "subject": subject, "body": body}})

def delete_template(template_id):
    templates_collection.delete_one({"_id": template_id})

# Function to create the sidebar navigation
def sidebar_navigation(main_option): 

    st.sidebar.title("Dashboard")    
    
    sub_option = None  # Initialize sub_option to ensure it's always defined
    
    if main_option == "Email":
        sub_option = st.sidebar.radio("Gmail Options", 
                                       ["Home","Compose Email", "Groups", 
                                        "CSV Management", "Templates", 
                                        "Sent Mails", "Failed Mails", 
                                        "Spam", "Logout"],
                                       index=0,  # Set default selection if needed
                                       format_func=lambda x: f"{x}")  # Format option text
    elif main_option == "Outlook":
        sub_option = st.sidebar.radio("Outlook Options", 
                                       ["Home","Compose Email", "Groups", 
                                        "CSV Management", "Templates", 
                                        "Sent Mails", "Failed Mails", 
                                        "Spam", "Logout"],
                                       index=0,  # Set default selection if needed
                                       format_func=lambda x: f"{x}")  # Format option text
    else:
        st.error("Invalid main option selected.")  # Handle unexpected main_option

    return main_option, sub_option

def display_mails(platform, status):
    # Apply custom CSS

    # Section title based on platform
    platform_section = "Gmail" if platform.lower() == "gmail" else "Outlook"
    section_class = "gmail-section" if platform.lower() == "gmail" else "outlook-section"

    with st.container():
        # Display platform-specific title
        st.markdown(f"<h2 class='{section_class}'>{platform_section} - {status.capitalize()} Mails</h2>", unsafe_allow_html=True)

        # Fetch mails from the collection based on platform and status
        mails = mails_collection.find({"status": status, "platform": platform})

        # Display each mail
        for mail in mails:
            recipients = mail.get('recipients', [])
            flat_recipients = [str(recipient) for recipient in recipients]

            # Render each mail as a card
            st.markdown(f"""
                <div class="mail-card">
                    <div class="mail-header">Platform: {mail.get('platform', 'N/A')}</div>
                    <div class="mail-header">Timestamp: {mail.get('timestamp', 'N/A')}</div>
                    <div class="mail-header">Recipients: {', '.join(flat_recipients)}</div>
                </div>
            """, unsafe_allow_html=True)



def group_management():
      # Inject the custom CSS

    st.title("Manage Email Groups")

    # Create a container for the group management section
    with st.container():
        st.markdown('<div class="group-container">', unsafe_allow_html=True)

        # Initialize state for group updates
        if 'update_group_id' in st.session_state:
            # Populate fields with existing group data for updating
            group_name = st.text_input("Group Name", value=st.session_state.update_group_name)
            email_list = st.text_area("Recipients (comma separated)", value=st.session_state.update_group_recipients)

            # Update button logic
            if st.button("Confirm Update"):
                emails = [email.strip() for email in email_list.split(",") if email.strip()]
                if group_name and emails:
                    update_group(st.session_state.update_group_id, group_name, emails)
                    st.success("Group updated successfully!")

                    # Clear session state for updating after successful update
                    del st.session_state.update_group_id
                    del st.session_state.update_group_name
                    del st.session_state.update_group_recipients
                else:
                    st.error("Please provide a valid group name and at least one email.")
        else:
            # Form for creating a new group
            group_name = st.text_input("Group Name")
            email_list = st.text_area("Recipients (comma separated)")

            if st.button("Create Group"):
                emails = [email.strip() for email in email_list.split(",") if email.strip()]
                if group_name and emails:
                    create_group(group_name, emails, user_id="example_user_id")  # Use the actual user_id
                    st.success("Group created successfully!")
                else:
                    st.error("Please provide a valid group name and at least one email.")

        # Search groups
        search_term = st.text_input("Search Groups by Name", "")
        user_groups = get_user_groups(user_id="example_user_id", search_term=search_term)

        st.header("Existing Groups")
        st.write("Your Groups:")

        for group in user_groups:
            # Card structure for each group
            st.markdown(f"""
                <div class="template-card">
                    <div class="template-header">Group Name: {group['group_name']}</div>
                    <div class="template-body"><strong>Emails:</strong> {', '.join(group['emails'])}</div>
              
                </div>
            """, unsafe_allow_html=True)

            # Handling button actions
            if st.button("Delete", key=f"delete_{group['_id']}"):
                email_groups.delete_one({"_id": group['_id']})  # Use _id for deletion
                st.success(f"Group '{group['group_name']}' deleted successfully!")
                st.rerun()  # Refresh the app to reflect changes

            if st.button("Update", key=f"update_{group['_id']}"):
                st.session_state.update_group_id = group["_id"]
                st.session_state.update_group_name = group["group_name"]
                st.session_state.update_group_recipients = ", ".join(group["emails"])
                st.rerun()  # Refresh to allow user to update group

        # Optional: Clear update state button
        if st.button("Clear Update"):
            if 'update_group_id' in st.session_state:
                del st.session_state.update_group_id
                del st.session_state.update_group_name
                del st.session_state.update_group_recipients

        st.markdown('</div>', unsafe_allow_html=True)
  # Close the container
  # Close the container


def gmail_home():
    # Add Gmail-specific stats and charts here
    dashboard_home("gmail")

def outlook_home():
    # Add Outlook-specific stats and charts here
    dashboard_home("outlook")

# custom_css2 = """
# <style>
#      .template-header, .stMetric {
#         color: black !important; /* Ensure all text and metric colors are black */
#     }
#     .stMetric-value {
#         color: black !important;
#     }
# </style>
# """
def dashboard_home(mail_type):
    with st.container():

        st.title(f"{mail_type.capitalize()} Email Dashboard")
        stats = get_mail_stats(mail_type)  # Function to get email stats for the specified type
    
        # Display the metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Mails Today", stats['today'])
        col2.metric("Total Mails Sent", stats['total'])
        col3.metric("Sent Mails", stats['sent'])
        col4.metric("Failed Mails", stats['failed'])
        st.metric("Spam Mails", stats['spam'])
    
        # Daily Email Stats (chart) and Refresh
        daily_counts = get_daily_email_counts(mail_type)
        dates = list(daily_counts.keys())
        counts = list(daily_counts.values())
    
        plt.figure(figsize=(10, 5))
        plt.bar(dates, counts, color='skyblue')
        plt.title(f'Daily {mail_type.capitalize()} Emails Sent')
        plt.xlabel('Date')
        plt.ylabel('Number of Emails Sent')
        plt.xticks(rotation=45)
        st.pyplot(plt)
    
        if st.button('Refresh Data'):
            st.rerun() # This will re-run the entire script to fetch fresh data
    
    
# CS    V Management Page
def delete_csv_record(file_name):
    """Delete the CSV record from the database."""
    csv_records.delete_one({"file_name": file_name})



def template_management():

    st.title("Template Management")

    # Form for adding new templates
    st.subheader("Add New Template")
    name = st.text_input("Template Name")
    subject = st.text_input("Email Subject")
    body = st.text_area("Email Body")

    if st.button("Save Template"):
        if name and subject and body:
            create_template(name, subject, body)
            st.success("Template added successfully!")
            st.rerun()  # Refresh the page to show the new template
        else:
            st.error("Please fill out all fields to save the template.")

    # Display existing templates
    templates = get_templates()
    if templates:
        st.subheader("Existing Templates")
        for template in templates:
            st.markdown(f"""
                <div class="template-card">
                    <div class="template-header">Template Name: {template['name']}</div>
                    <div class="template-body"><strong>Subject:</strong> {template['subject']}</div>
                    <div class="template-body"><strong>Body:</strong> {template['body']}</div>
                    <div class="button-container">
                        <button id="delete_{template['_id']}">Delete</button>
                        <button id="update_{template['_id']}">Update</button>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            # Buttons for Update and Delete actions
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("Delete", key=f"delete_{template['_id']}"):
                    delete_template(template["_id"])
                    st.success(f"Template '{template['name']}' deleted successfully!")
                    st.rerun()

            with col2:
                if st.button("Update", key=f"update_{template['_id']}"):
                    st.session_state.update_template_id = template["_id"]
                    st.session_state.update_template_name = template["name"]
                    st.session_state.update_template_subject = template["subject"]
                    st.session_state.update_template_body = template["body"]
                    st.rerun()

    # Update existing template form
    if "update_template_id" in st.session_state:
        st.subheader("Update Template")
        updated_name = st.text_input("Template Name", value=st.session_state.update_template_name)
        updated_subject = st.text_input("Email Subject", value=st.session_state.update_template_subject)
        updated_body = st.text_area("Email Body", value=st.session_state.update_template_body)

        if st.button("Save Changes"):
            update_template(st.session_state.update_template_id, updated_name, updated_subject, updated_body)
            st.success("Template updated successfully!")
            # Clear the update form
            for key in ["update_template_id", "update_template_name", "update_template_subject", "update_template_body"]:
                st.session_state.pop(key, None)
            st.rerun()


    if 'update_template_id' in st.session_state:
        template_name = st.text_input("Template Name", value=st.session_state.update_template_name,key="tem")
        template_subject = st.text_input("Template Subject", value=st.session_state.update_template_subject)
        template_body = st.text_area("Template Body", value=st.session_state.update_template_body)

        if st.button("Confirm Update"):
            update_template(st.session_state.update_template_id, template_name, template_subject, template_body)
            st.success("Template updated successfully!")
            del st.session_state.update_template_id
            del st.session_state.update_template_name
            del st.session_state.update_template_subject
            del st.session_state.update_template_body
def store_csv_record(file_name, emails, phone_numbers):
    csv_records.insert_one({
        "file_name": file_name,
        "emails": emails,
        "phone_numbers": phone_numbers
    })
def extract_contacts_from_csv(csv_file):
    emails = []
    phone_numbers = []
    df = pd.read_csv(csv_file)

    # Assume emails and phone numbers have specific column names, e.g., "Email" and "Phone"
    if 'Email' in df.columns:
        emails = df['Email'].dropna().tolist()
    if 'Phone' in df.columns:
        phone_numbers = df['Phone'].dropna().tolist()

    return emails, phone_numbers



def get_csv_records():
    return list(csv_records.find())
def csv_management():
    st.title("Upload CSV File")
    
    with st.container():
        uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])

        # If a file is uploaded, extract emails and phone numbers and store the record
        if uploaded_file:
            file_name = uploaded_file.name
            emails, phone_numbers = extract_contacts_from_csv(uploaded_file)  # Updated function
            
            if emails or phone_numbers:
                # Check if the file already exists in the records to avoid duplicates
                if not csv_records.find_one({"file_name": file_name}):
                    store_csv_record(file_name, emails, phone_numbers)  # Store both emails and phone numbers
                    st.success(f"Successfully extracted {len(emails)} emails and {len(phone_numbers)} phone numbers from {file_name}!")
                else:
                    st.warning(f"The file '{file_name}' already exists.")
            else:
                st.error("No emails or phone numbers found in the uploaded CSV file.")

        # Display CSV files with extracted contacts
        st.header("CSV Files with Extracted Contacts")
        csv_files = get_csv_records()

        # Initialize session state for email display management
        if 'display_emails' not in st.session_state:
            st.session_state.display_emails = False
            st.session_state.selected_csv = None

        if csv_files:
            # Create a unique list of CSV file names to avoid duplicates
            csv_file_names = [record["file_name"] for record in csv_files]

            # Selectbox for choosing CSV files
            selected_csv = st.selectbox("Select a CSV file to view contacts", csv_file_names, key="csv_selectbox")

            if st.button("View Contacts"):
                st.session_state.selected_csv = selected_csv
                st.session_state.display_emails = True  # Set state to show contacts

            # Display contacts if requested
            if st.session_state.display_emails and st.session_state.selected_csv:
                selected_record = next(record for record in csv_files if record["file_name"] == st.session_state.selected_csv)
                st.write(f"Contacts from {st.session_state.selected_csv}:")

                # Display emails and phone numbers in editable format
                updated_emails = st.text_area("Edit Emails (comma-separated)", value=", ".join(selected_record.get("emails", [])), height=100)
                # updated_phone_numbers = st.text_area("Edit Phone Numbers (comma-separated)", value=", ".join(selected_record.get("phone_numbers", [])), height=100)

                # Button to update the contacts
                if st.button("Update Contacts"):
                    # Split and clean the updated emails and phone numbers
                    updated_email_list = [email.strip() for email in updated_emails.split(",") if email.strip()]
                    # updated_phone_list = [phone.strip() for phone in updated_phone_numbers.split(",") if phone.strip()]

                    # Update the record in MongoDB
                    csv_records.update_one(
                        {"file_name": st.session_state.selected_csv},
                        {"$set": {"emails": updated_email_list}}
                    )
                    st.success("Contacts updated successfully!")
                    # Refresh the display
                    st.session_state.display_emails = False
                    st.session_state.selected_csv = None
                    st.session_state.display_emails = True

                # Display the updated contacts
                else:
                    st.write("Existing Emails:")
                    for email in selected_record.get("emails", []):
                        st.write(email)
                    
                    st.write("Existing Phone Numbers:")
                    for phone in selected_record.get("phone_numbers", []):
                        st.write(phone)

                # Button to close display of contacts
                if st.button("Close Display"):
                    st.session_state.display_emails = False
                    st.session_state.selected_csv = None

            # Option to delete CSV file
            if st.button("Delete CSV File"):
                delete_csv_record(selected_csv)
                st.success(f"CSV file '{selected_csv}' deleted successfully.")
                csv_files = get_csv_records()  # Refresh CSV records

        else:
            st.warning("No CSV files uploaded yet.")



def get_phone_numbers():
    # Your existing code to fetch phone numbers from MongoDB
    phone_numbers_dict = {}
    for record in csv_records.find():
        name = record.get("name")
        phone_numbers = record.get("phone_numbers", [])
        phone_numbers_dict[name] = phone_numbers
    return phone_numbers_dict

def email_dashboard(platform): 

    with st.container():

        # Use the platform-specific class for the dashboard
        st.title(f"Write a mail ....!")

        # Template selection and inputs
        st.subheader("Select a Saved Template")
        templates = get_templates()  # Fetch templates from the database
        template_options = ["No Template"] + [template["name"] for template in templates]
        selected_template = st.selectbox("Choose a Template", template_options,key="template")

        # Initialize subject and body based on selected template
        if selected_template != "No Template":
            template_data = next(template for template in templates if template["name"] == selected_template)
            subject = template_data["subject"]
            body = template_data["body"]
        else:
            subject = ""
            body = ""

        # Subject and body input fields
        subject = st.text_input("Subject", value=subject)
        body = st.text_area("Message", value=body)

        # Template saving feature
        st.subheader("Save Current Email as Template")
        template_name = st.text_input("Template Name (optional for saving)")
        if st.button("Save Template"):
            if template_name:
                create_template(template_name, subject, body)  # Function to save the template to the database
                st.success(f"Template '{template_name}' saved successfully!")
            else:
                st.error("Please provide a template name.")

        # Group selection
        groups = get_groups()
        group_options = list(groups.keys()) + ["No Group"]
        selected_group = st.selectbox("Choose a Group", group_options, key=platform)

        # Manual email input
        manual_email_input = st.text_area("Or enter manual email addresses (comma-separated):")

        # Get CSV records for the email dashboard
        csv_files = get_csv_records()
        csv_options = [record["file_name"] for record in csv_files] + ["No CSV"]
        selected_csv = st.selectbox("Select CSV File for Emails", csv_options,key="selected")

        # Send email button in styled container
        with st.container():
            st.markdown('<div class="send-button">', unsafe_allow_html=True)
            if st.button(f"Send Email via {platform}"):
                recipients = []

                if selected_group != "No Group":
                    recipients = groups.get(selected_group, [])

                if manual_email_input:
                    manual_emails = [email.strip() for email in manual_email_input.split(",") if email.strip()]
                    recipients.extend(manual_emails)

                if selected_csv != "No CSV":
                    selected_record = next(record for record in csv_files if record["file_name"] == selected_csv)
                    recipients.extend(selected_record["emails"])

                if recipients:
                    if platform == "Email":
                        smtp_info = ("smtp.gmail.com", 587, "tt0234240@gmail.com", "qfox itjg sfae xxgy")  # Replace with real password
                    elif platform=="Outlook":
                        smtp_info = ("smtp.office365.com", 587, "support@aptpath.in", "kjydtmsbmbqtnydk")  # Replace with real password
                    
                    send_email_smtp(subject, body, recipients, smtp_info)
                    st.success("Email sent successfully!")
                    st.rerun()
                else:
                    st.error("Please provide at least one recipient email address.")
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)  # Close main container


def login_page():
    # Set the page title


    # Image background

    # Login form
    with st.container():
        st.title("Login")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if authenticate_user(email, password):
                st.session_state.page = "choose service"
                st.rerun()
            else:
                st.error("Invalid email or password.")

        if st.button("Go to Sign Up"):
            st.session_state.page = "Register"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

def navigate_to(page):
    st.session_state.page = page
    # Signup page
def signup_page():
    st.title("Sign Up")
    new_email = st.text_input("New Email")
    new_password = st.text_input("New Password", type="password")
    
    if st.button("Register"):
        register_user(new_email, new_password)

    if st.button("Go to Login"):
        st.session_state.page = "Login" 
def demo():
    st.title("outlook")
def choose_service_page():
    st.title("Choose Service")
    st.write("Choose Email or Outlook.")
    user_choice = st.radio("Select Service:", ["Email", "Outlook"])
    st.session_state.user_choice = user_choice
    if st.button("Continue"):
        if user_choice == "Email":
            st.session_state.page="EmailDashboard"
        elif user_choice == "Outlook":
            st.session_state.page="outlookDashboard"
    
def gmail_dashboard(sub_option):
    if sub_option == "Home":
        gmail_home()
    if sub_option=="Compose Email":
        email_dashboard("Email")
    elif sub_option == "Groups":
        group_management()
    elif sub_option == "CSV Management":
        csv_management()
    elif sub_option == "Templates":
        template_management()
    elif sub_option == "Sent Mails":
        display_mails('gmail','sent')
    elif sub_option == "Failed Mails":
        display_mails('gmail','failed')
    elif sub_option == "Spam":
        display_mails('gmail','spam')
    elif sub_option == "Logout":
        st.session_state.page = "Login"
        st.rerun()

def outlook_dashboard(sub_option):
    if sub_option == "Home":
        outlook_home()
    if sub_option=="Compose Email":
        email_dashboard("Outlook")
    elif sub_option == "Groups":
        group_management()
    elif sub_option == "CSV Management":
        csv_management()
    elif sub_option == "Templates":
        template_management()
    elif sub_option == "Sent Mails":
        display_mails('outlook','sent')
    elif sub_option == "Failed Mails":
        display_mails('outlook','failed')
    elif sub_option == "Spam":
        display_mails('outlook','spam')
    elif sub_option == "Logout":
        st.session_state.page = "Login"
        st.rerun()
def main():
    # Initialize session state variables
    if "page" not in st.session_state:
        st.session_state.page = "Login"
    if "user_choice" not in st.session_state:
        st.session_state.user_choice = None
    elif st.session_state.page == "Login":
        login_page()
    elif st.session_state.page == "Register":
        signup_page()
    elif st.session_state.page == "choose service":
        choose_service_page()
    elif st.session_state.page == "EmailDashboard" and st.session_state.user_choice == "Email":
        main_option,suboption = sidebar_navigation("Email")
        if main_option:
            gmail_dashboard(suboption)
    elif st.session_state.page == "outlookDashboard" and st.session_state.user_choice == "Outlook":
        main_option,suboption = sidebar_navigation("Outlook")
        if main_option:
            gmail_dashboard(suboption)
            print(suboption)

if __name__ == "__main__":
    main()
