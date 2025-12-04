import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'leads_magics.settings')
django.setup()

from campaigns.models import *

def setup_initial_data():
    # Create a company
    company, created = Company.objects.get_or_create(
        company_name="Example Corp",
        defaults={
            'domain': 'example.com',
            'location': 'New York',
            'industry': 'Technology'
        }
    )
    
    # Create some clients
    clients_data = [
        {'client': 'John Doe', 'email': 'john@example.com', 'job_role': 'CEO'},
        {'client': 'Jane Smith', 'email': 'jane@example.com', 'job_role': 'CTO'},
        {'client': 'Bob Johnson', 'email': 'bob@example.com', 'job_role': 'Manager'},
    ]
    
    for data in clients_data:
        Client.objects.get_or_create(
            email=data['email'],
            defaults={
                'company': company,
                'client': data['client'],
                'job_role': data['job_role'],
                'status': 'active'
            }
        )
    
    # Create lists
    list1, _ = List.objects.get_or_create(name='VIP Customers')
    list2, _ = List.objects.get_or_create(name='Newsletter Subscribers')
    
    # Add clients to lists
    for client in Client.objects.all():
        list1.clients.add(client)
    
    # Create template category
    category, _ = EmailTemplateCategory.objects.get_or_create(name='Marketing')
    
    # Create email template
    template, _ = EmailTemplate.objects.get_or_create(
        name='Welcome Email',
        defaults={
            'category': category,
            'subject': 'Welcome to Our Service!',
            'content': '<h1>Welcome {{name}}!</h1><p>Thank you for joining us.</p>'
        }
    )
    
    print(f"Company ID: {company.id}")
    print(f"Template ID: {template.id}")
    print(f"List IDs: {list1.id}, {list2.id}")
    print("Setup complete!")

if __name__ == '__main__':
    setup_initial_data()