from models import db, User, Customer, Segment, Campaign, CampaignResult, CampaignActivity
from datetime import datetime
import json
import random
import math
import hashlib
import redis
from flask import current_app

# =============================================================================
# Event Bus (Redis Pub/Sub)
# =============================================================================
class EventBus:
    _instance = None
    _redis_client = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = EventBus()
            # Initialize Redis connection
            try:
                cls._redis_client = redis.from_url(current_app.config['REDIS_URL'])
            except Exception as e:
                print(f"⚠️ Warning: Could not connect to Redis: {e}")
                cls._redis_client = None
        return cls._instance

    def publish(self, event_name, data):
        """Publish an event to the Redis channel"""
        if not self._redis_client:
            print(f"⚠️ Event Bus disabled (No Redis): Dropping event {event_name}")
            return

        message = {
            'event': event_name,
            'timestamp': datetime.utcnow().isoformat(),
            'data': data
        }
        
        try:
            # Publish to a general 'crm_events' channel or specific ones
            self._redis_client.publish('crm_events', json.dumps(message))
            print(f"📣 [EventBus] Published: {event_name}")
        except Exception as e:
            print(f"❌ [EventBus] Failed to publish: {e}")


# =============================================================================
# Authentication Services
# =============================================================================
def hash_password(password):
    """Simple password hashing (use bcrypt in production)"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, password_hash):
    """Verify password against hash"""
    return hash_password(password) == password_hash


def create_user(username, password, email=None, role='marketer'):
    """Create a new user"""
    user = User(
        username=username,
        password_hash=hash_password(password),
        email=email,
        role=role
    )
    db.session.add(user)
    db.session.commit()
    return user


def authenticate_user(username, password):
    """Authenticate user and return user object if valid"""
    user = User.query.filter_by(username=username).first()
    if user and verify_password(password, user.password_hash):
        return user
    return None


def get_user_by_id(user_id):
    """Get user by ID"""
    return User.query.get(user_id)


# =============================================================================
# Customer Services
# =============================================================================
def create_customer(name, email, phone=None, demographics=None, status='lead', lead_source=None):
    """Create a new customer"""
    customer = Customer(
        name=name,
        email=email,
        phone=phone,
        status=status,
        lead_source=lead_source
    )
    if demographics:
        customer.set_demographics(demographics)
    
    db.session.add(customer)
    db.session.commit()
    return customer


def get_all_customers(page=1, per_page=50, status=None, search=None):
    """Get customers with optional filtering and pagination"""
    query = Customer.query
    
    if status:
        query = query.filter_by(status=status)
    
    if search:
        search_term = f'%{search}%'
        query = query.filter(
            (Customer.name.ilike(search_term)) | 
            (Customer.email.ilike(search_term))
        )
    
    return query.order_by(Customer.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )


def get_customer_by_id(customer_id):
    """Get customer by ID"""
    return Customer.query.get(customer_id)


def update_customer(customer_id, **kwargs):
    """Update customer fields"""
    customer = Customer.query.get(customer_id)
    if not customer:
        return None
    
    for key, value in kwargs.items():
        if key == 'demographics':
            customer.set_demographics(value)
        elif key == 'purchase_history':
            customer.set_purchase_history(value)
        elif key == 'behavioral_data':
            customer.set_behavioral_data(value)
        elif hasattr(customer, key):
            setattr(customer, key, value)
    
    db.session.commit()
    return customer


# =============================================================================
# Segmentation Services
# =============================================================================
def create_segment(name, criteria, description=None, segment_type='manual'):
    """Create a new segment with criteria"""
    segment = Segment(
        name=name,
        description=description,
        segment_type=segment_type
    )
    
    if isinstance(criteria, dict):
        segment.set_criteria(criteria)
    else:
        segment.criteria = criteria if isinstance(criteria, str) else json.dumps(criteria)
    
    db.session.add(segment)
    db.session.commit()
    
    # Calculate initial customer count
    refresh_segment(segment.id)
    
    return segment


def get_all_segments():
    """Get all active segments"""
    return Segment.query.filter_by(is_active=True).all()


def get_segment_by_id(segment_id):
    """Get segment by ID"""
    return Segment.query.get(segment_id)


def update_segment(segment_id, **kwargs):
    """Update segment fields"""
    segment = Segment.query.get(segment_id)
    if not segment:
        return None
    
    for key, value in kwargs.items():
        if key == 'criteria':
            segment.set_criteria(value) if isinstance(value, dict) else setattr(segment, key, value)
        elif hasattr(segment, key):
            setattr(segment, key, value)
    
    db.session.commit()
    refresh_segment(segment_id)
    return segment


def evaluate_segment_criteria(customer, criteria):
    """
    Evaluate if a customer matches segment criteria
    Criteria format: {"rules": [{"field": "demographics.age", "operator": "gt", "value": 25}], "match": "all"}
    """
    if isinstance(criteria, str):
        try:
            criteria = json.loads(criteria)
        except:
            return True  # If no valid criteria, include all
    
    rules = criteria.get('rules', [])
    match_type = criteria.get('match', 'all')  # 'all' or 'any'
    
    if not rules:
        return True
    
    results = []
    for rule in rules:
        field_path = rule.get('field', '')
        operator = rule.get('operator', 'eq')
        value = rule.get('value')
        
        # Get the actual value from customer
        actual_value = get_nested_value(customer, field_path)
        
        # Evaluate the rule
        result = evaluate_rule(actual_value, operator, value)
        results.append(result)
    
    if match_type == 'all':
        return all(results)
    else:  # 'any'
        return any(results)


def get_nested_value(customer, field_path):
    """Get nested value from customer object using dot notation"""
    parts = field_path.split('.')
    
    if parts[0] == 'demographics':
        data = customer.get_demographics()
        return data.get(parts[1]) if len(parts) > 1 else data
    elif parts[0] == 'behavioral_data':
        data = customer.get_behavioral_data()
        return data.get(parts[1]) if len(parts) > 1 else data
    elif parts[0] == 'purchase_history':
        return customer.get_purchase_history()
    else:
        return getattr(customer, parts[0], None)


def evaluate_rule(actual_value, operator, expected_value):
    """Evaluate a single rule"""
    if actual_value is None:
        return False
    
    try:
        if operator == 'eq':
            return actual_value == expected_value
        elif operator == 'neq':
            return actual_value != expected_value
        elif operator == 'gt':
            return float(actual_value) > float(expected_value)
        elif operator == 'gte':
            return float(actual_value) >= float(expected_value)
        elif operator == 'lt':
            return float(actual_value) < float(expected_value)
        elif operator == 'lte':
            return float(actual_value) <= float(expected_value)
        elif operator == 'contains':
            return str(expected_value).lower() in str(actual_value).lower()
        elif operator == 'in':
            return actual_value in expected_value
        else:
            return False
    except (ValueError, TypeError):
        return False


def get_segment_customers(segment_id):
    """Get all customers matching a segment's criteria"""
    segment = Segment.query.get(segment_id)
    if not segment:
        return []
    
    criteria = segment.get_criteria()
    all_customers = Customer.query.all()
    matching_customers = []
    
    for customer in all_customers:
        if evaluate_segment_criteria(customer, criteria):
            matching_customers.append(customer)
    
    return matching_customers


def refresh_segment(segment_id):
    """Recalculate segment membership count"""
    segment = Segment.query.get(segment_id)
    if not segment:
        return None
    
    matching_customers = get_segment_customers(segment_id)
    segment.customer_count = len(matching_customers)
    db.session.commit()
    
    return segment


# =============================================================================
# Campaign Services
# =============================================================================
def create_campaign(name, segment_id, campaign_type='email', subject=None, content=None, 
                    schedule_time=None, budget=0.0, description=None):
    """Create a new campaign"""
    campaign = Campaign(
        name=name,
        description=description,
        campaign_type=campaign_type,
        subject=subject,
        content=content,
        segment_id=segment_id,
        schedule_time=schedule_time,
        budget=budget
    )
    
    # Create empty result entry
    result = CampaignResult(campaign=campaign)
    
    db.session.add(campaign)
    db.session.add(result)
    db.session.commit()
    
    # Publish Event: [CampaignCreated]
    # As per C&C Diagram: Notify other services (e.g. Sales)
    with current_app.app_context():
        EventBus.get_instance().publish('CampaignCreated', {
            'campaign_id': campaign.id,
            'name': campaign.name,
            'type': campaign.campaign_type,
            'budget': campaign.budget,
            'segment_id': segment_id
        })
    
    return campaign


def resume_campaign(campaign_id):
    """Resume a paused campaign"""
    campaign = Campaign.query.get(campaign_id)
    if campaign and campaign.status == 'paused':
        campaign.status = 'active'
        db.session.commit()
    return campaign


def get_all_campaigns(status=None):
    """Get all campaigns, optionally filtered by status"""
    query = Campaign.query
    if status:
        query = query.filter_by(status=status)
    return query.order_by(Campaign.created_at.desc()).all()


def get_campaign_by_id(campaign_id):
    """Get campaign by ID"""
    return Campaign.query.get(campaign_id)


def update_campaign(campaign_id, **kwargs):
    """Update campaign fields"""
    campaign = Campaign.query.get(campaign_id)
    if not campaign:
        return None
    
    for key, value in kwargs.items():
        if key == 'workflow_steps':
            campaign.set_workflow_steps(value)
        elif key == 'schedule_time' and value:
            if isinstance(value, str):
                campaign.schedule_time = datetime.fromisoformat(value)
            else:
                campaign.schedule_time = value
        elif hasattr(campaign, key):
            setattr(campaign, key, value)
    
    db.session.commit()
    
    # Publish Event: [CampaignUpdate]
    with current_app.app_context():
        EventBus.get_instance().publish('CampaignUpdated', {
            'campaign_id': campaign.id,
            'name': campaign.name,
            'status': campaign.status,
            'updated_at': datetime.utcnow().isoformat()
        })

    return campaign


def launch_campaign(campaign_id):
    """Launch a campaign and simulate results"""
    campaign = Campaign.query.get(campaign_id)
    if not campaign:
        return None
    
    # Only launch if draft (if resuming, use resume_campaign)
    if campaign.status != 'draft':
         return campaign
    
    # Get target audience size
    segment_customers = get_segment_customers(campaign.segment_id)
    audience_size = len(segment_customers) if segment_customers else random.randint(100, 500)
    
    # Update campaign status
    campaign.status = 'active'
    campaign.start_date = datetime.utcnow()
    
    # Generate simulated results
    if campaign.results:
        results = campaign.results
        results.total_sent = audience_size
        results.delivered = int(audience_size * random.uniform(0.92, 0.98))  # 92-98% delivery rate
        results.bounced = results.total_sent - results.delivered
        
        # Engagement metrics based on campaign type
        if campaign.campaign_type == 'email':
            results.opens = int(results.delivered * random.uniform(0.15, 0.35))  # 15-35% open rate
            results.clicks = int(results.opens * random.uniform(0.10, 0.25))  # 10-25% click rate
        elif campaign.campaign_type == 'social':
            results.impressions = audience_size * random.randint(2, 5)
            results.opens = int(results.impressions * random.uniform(0.02, 0.08))  # Engagement
            results.clicks = int(results.opens * random.uniform(0.20, 0.40))
        else:  # ads
            results.impressions = audience_size * random.randint(5, 15)
            results.clicks = int(results.impressions * random.uniform(0.01, 0.05))  # 1-5% CTR
            results.opens = results.clicks
        
        # Conversions
        # Improve logic: for small numbers, ensure at least some conversions if we have enough clicks
        raw_conversions = results.clicks * random.uniform(0.05, 0.20)
        # If we have clicks but low conversion rate would yield 0, give a chance for 1 conversion
        if raw_conversions < 1 and results.clicks > 0 and random.random() > 0.5:
             results.conversions = 1
        else:
             results.conversions = int(math.ceil(raw_conversions))
             
        results.leads_generated = int(math.ceil(results.clicks * random.uniform(0.10, 0.30)))
        results.leads_converted = int(math.ceil(results.leads_generated * random.uniform(0.20, 0.40)))
        
        # Revenue (simulate)
        avg_order_value = random.uniform(50, 200)
        results.revenue_attributed = results.conversions * avg_order_value
        results.total_cost = results.total_sent * campaign.cost_per_send + (campaign.budget * 0.5)
    
    db.session.commit()
    return campaign


def pause_campaign(campaign_id):
    """Pause an active campaign"""
    campaign = Campaign.query.get(campaign_id)
    if campaign and campaign.status == 'active':
        campaign.status = 'paused'
        db.session.commit()
    return campaign


def complete_campaign(campaign_id):
    """Mark campaign as completed"""
    campaign = Campaign.query.get(campaign_id)
    if campaign:
        campaign.status = 'completed'
        campaign.end_date = datetime.utcnow()
        db.session.commit()
    return campaign


# =============================================================================
# Analytics Services
# =============================================================================
def get_campaign_stats(campaign_id):
    """Get detailed stats for a campaign"""
    campaign = Campaign.query.get(campaign_id)
    if not campaign or not campaign.results:
        return None
    return campaign.results.to_dict()


def get_analytics_overview():
    """Get overall marketing analytics dashboard data"""
    campaigns = Campaign.query.all()
    results = CampaignResult.query.all()
    
    total_campaigns = len(campaigns)
    active_campaigns = len([c for c in campaigns if c.status == 'active'])
    
    total_sent = sum(r.total_sent for r in results)
    total_opens = sum(r.opens for r in results)
    total_clicks = sum(r.clicks for r in results)
    total_conversions = sum(r.conversions for r in results)
    total_revenue = sum(r.revenue_attributed for r in results)
    total_cost = sum(r.total_cost for r in results)
    
    return {
        'total_campaigns': total_campaigns,
        'active_campaigns': active_campaigns,
        'completed_campaigns': len([c for c in campaigns if c.status == 'completed']),
        'draft_campaigns': len([c for c in campaigns if c.status == 'draft']),
        
        'total_sent': total_sent,
        'total_opens': total_opens,
        'total_clicks': total_clicks,
        'total_conversions': total_conversions,
        
        'overall_open_rate': (total_opens / total_sent * 100) if total_sent > 0 else 0,
        'overall_click_rate': (total_clicks / total_opens * 100) if total_opens > 0 else 0,
        'overall_conversion_rate': (total_conversions / total_clicks * 100) if total_clicks > 0 else 0,
        
        'total_revenue': total_revenue,
        'total_cost': total_cost,
        'overall_roi': ((total_revenue - total_cost) / total_cost * 100) if total_cost > 0 else 0,
        
        'total_customers': Customer.query.count(),
        'total_segments': Segment.query.filter_by(is_active=True).count(),
        'total_leads': Customer.query.filter_by(status='lead').count()
    }


def get_campaign_roi_report():
    """Get ROI breakdown by campaign"""
    campaigns = Campaign.query.filter(Campaign.status.in_(['active', 'completed'])).all()
    
    report = []
    for campaign in campaigns:
        if campaign.results:
            metrics = campaign.results.calculate_metrics()
            report.append({
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'campaign_type': campaign.campaign_type,
                'status': campaign.status,
                'revenue': metrics['revenue_attributed'],
                'cost': metrics['total_cost'],
                'roi': metrics['roi'],
                'conversions': metrics['conversions']
            })
    
    return sorted(report, key=lambda x: x['roi'], reverse=True)


def get_conversion_funnel():
    """Get conversion funnel data"""
    results = CampaignResult.query.all()
    
    total_sent = sum(r.total_sent for r in results)
    total_delivered = sum(r.delivered for r in results)
    total_opens = sum(r.opens for r in results)
    total_clicks = sum(r.clicks for r in results)
    total_leads = sum(r.leads_generated for r in results)
    total_conversions = sum(r.conversions for r in results)
    
    return {
        'stages': [
            {'name': 'Sent', 'count': total_sent, 'percentage': 100},
            {'name': 'Delivered', 'count': total_delivered, 
             'percentage': (total_delivered / total_sent * 100) if total_sent > 0 else 0},
            {'name': 'Opened', 'count': total_opens,
             'percentage': (total_opens / total_sent * 100) if total_sent > 0 else 0},
            {'name': 'Clicked', 'count': total_clicks,
             'percentage': (total_clicks / total_sent * 100) if total_sent > 0 else 0},
            {'name': 'Leads', 'count': total_leads,
             'percentage': (total_leads / total_sent * 100) if total_sent > 0 else 0},
            {'name': 'Converted', 'count': total_conversions,
             'percentage': (total_conversions / total_sent * 100) if total_sent > 0 else 0}
        ]
    }


def get_segment_performance():
    """Get performance by segment"""
    segments = Segment.query.filter_by(is_active=True).all()
    
    performance = []
    for segment in segments:
        campaigns = Campaign.query.filter_by(segment_id=segment.id).all()
        
        total_conversions = 0
        total_revenue = 0
        total_campaigns = len(campaigns)
        
        for campaign in campaigns:
            if campaign.results:
                total_conversions += campaign.results.conversions
                total_revenue += campaign.results.revenue_attributed
        
        performance.append({
            'segment_id': segment.id,
            'segment_name': segment.name,
            'customer_count': segment.customer_count,
            'total_campaigns': total_campaigns,
            'total_conversions': total_conversions,
            'total_revenue': total_revenue
        })
    
    return sorted(performance, key=lambda x: x['total_revenue'], reverse=True)


# =============================================================================
# Sample Data Generation
# =============================================================================
def generate_sample_customers(count=50):
    """Generate sample customer data for demonstration"""
    first_names = ['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emily', 'Chris', 'Lisa', 
                   'Robert', 'Amanda', 'James', 'Jennifer', 'William', 'Jessica', 'Daniel']
    last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 
                  'Davis', 'Rodriguez', 'Martinez', 'Anderson', 'Taylor', 'Thomas', 'Moore']
    
    locations = ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 'Philadelphia',
                 'San Antonio', 'San Diego', 'Dallas', 'San Jose']
    
    lead_sources = ['Website', 'Social Media', 'Referral', 'Email Campaign', 'Google Ads', 'Trade Show']
    statuses = ['lead', 'prospect', 'customer', 'customer', 'customer']  # More likely to be customer
    
    customers = []
    for i in range(count):
        first = random.choice(first_names)
        last = random.choice(last_names)
        name = f"{first} {last}"
        email = f"{first.lower()}.{last.lower()}{i}@example.com"
        
        age = random.randint(22, 65)
        income = random.choice(['low', 'medium', 'high'])
        
        demographics = {
            'age': age,
            'gender': random.choice(['male', 'female']),
            'location': random.choice(locations),
            'income_bracket': income
        }
        
        total_spent = random.uniform(0, 5000) if random.random() > 0.3 else 0
        
        customer = Customer(
            name=name,
            email=email,
            phone=f"+1-555-{random.randint(100,999)}-{random.randint(1000,9999)}",
            status=random.choice(statuses),
            lead_source=random.choice(lead_sources),
            total_spent=round(total_spent, 2),
            lifetime_value=round(total_spent * random.uniform(1.2, 2.5), 2),
            engagement_score=random.randint(10, 100)
        )
        customer.set_demographics(demographics)
        customer.set_behavioral_data({
            'website_visits': random.randint(1, 50),
            'email_opens': random.randint(0, 20),
            'last_activity_days': random.randint(1, 90)
        })
        customer.set_purchase_history([
            {'product': f'Product {j}', 'amount': random.uniform(10, 200), 'date': '2024-01-15'}
            for j in range(random.randint(0, 5))
        ])
        
        customers.append(customer)
    
    db.session.add_all(customers)
    db.session.commit()
    
    return customers


def initialize_demo_data():
    """Initialize demo data if database is empty"""
    # Check if already initialized
    if Customer.query.first() is not None:
        return False
    
    # Create demo user
    if not User.query.filter_by(username='admin').first():
        create_user('admin', 'admin123', 'admin@example.com', 'admin')
    
    # Generate customers
    generate_sample_customers(50)
    
    # Create sample segments
    segment1 = create_segment(
        name='High Value Customers',
        description='Customers who have spent more than $1000',
        criteria={'rules': [{'field': 'total_spent', 'operator': 'gt', 'value': 1000}], 'match': 'all'},
        segment_type='purchase'
    )
    
    segment2 = create_segment(
        name='Young Professionals',
        description='Customers aged 25-40',
        criteria={'rules': [
            {'field': 'demographics.age', 'operator': 'gte', 'value': 25},
            {'field': 'demographics.age', 'operator': 'lte', 'value': 40}
        ], 'match': 'all'},
        segment_type='demographic'
    )
    
    segment3 = create_segment(
        name='Engaged Users',
        description='Highly engaged customers',
        criteria={'rules': [{'field': 'engagement_score', 'operator': 'gte', 'value': 70}], 'match': 'all'},
        segment_type='behavioral'
    )
    
    segment4 = create_segment(
        name='New Leads',
        description='Recently acquired leads',
        criteria={'rules': [{'field': 'status', 'operator': 'eq', 'value': 'lead'}], 'match': 'all'},
        segment_type='manual'
    )
    
    # Create sample campaigns
    campaign1 = create_campaign(
        name='Summer Sale 2024',
        segment_id=segment1.id,
        campaign_type='email',
        subject='Exclusive Summer Deals Just for You!',
        content='Dear valued customer, enjoy 20% off on all products this summer!',
        budget=500.0,
        description='Annual summer promotion targeting high-value customers'
    )
    
    campaign2 = create_campaign(
        name='Product Launch - Social',
        segment_id=segment2.id,
        campaign_type='social',
        content='Introducing our revolutionary new product line! #NewArrivals',
        budget=1000.0,
        description='Social media campaign for new product launch'
    )
    
    campaign3 = create_campaign(
        name='Re-engagement Campaign',
        segment_id=segment3.id,
        campaign_type='email',
        subject='We miss you! Come back for a special offer',
        content='Hi there! It\'s been a while. Here\'s 15% off your next order.',
        budget=300.0,
        description='Win-back campaign for engaged but inactive users'
    )
    
    # Launch one campaign to show results
    launch_campaign(campaign1.id)
    complete_campaign(campaign1.id)
    
    launch_campaign(campaign2.id)
    
    return True
