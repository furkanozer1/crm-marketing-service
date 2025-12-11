from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

# =============================================================================
# User Model (for Authentication)
# =============================================================================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    role = db.Column(db.String(20), default='marketer')  # admin, marketer, analyst
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.isoformat()
        }


# =============================================================================
# Customer Model (Single Source of Truth for Customer Data)
# =============================================================================
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Basic Info
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    
    # Demographics (JSON): age, gender, location, income_bracket, etc.
    demographics = db.Column(db.Text, nullable=True)
    
    # Purchase History (JSON): list of {product, amount, date}
    purchase_history = db.Column(db.Text, nullable=True)
    
    # Behavioral Data (JSON): website_visits, email_opens, last_activity, etc.
    behavioral_data = db.Column(db.Text, nullable=True)
    
    # Calculated Fields
    total_spent = db.Column(db.Float, default=0.0)
    lifetime_value = db.Column(db.Float, default=0.0)
    engagement_score = db.Column(db.Integer, default=0)  # 0-100
    
    # Status
    status = db.Column(db.String(20), default='lead')  # lead, prospect, customer, churned
    lead_source = db.Column(db.String(50), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_demographics(self):
        return json.loads(self.demographics) if self.demographics else {}
    
    def set_demographics(self, data):
        self.demographics = json.dumps(data)
    
    def get_purchase_history(self):
        return json.loads(self.purchase_history) if self.purchase_history else []
    
    def set_purchase_history(self, data):
        self.purchase_history = json.dumps(data)
    
    def get_behavioral_data(self):
        return json.loads(self.behavioral_data) if self.behavioral_data else {}
    
    def set_behavioral_data(self, data):
        self.behavioral_data = json.dumps(data)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'demographics': self.get_demographics(),
            'purchase_history': self.get_purchase_history(),
            'behavioral_data': self.get_behavioral_data(),
            'total_spent': self.total_spent,
            'lifetime_value': self.lifetime_value,
            'engagement_score': self.engagement_score,
            'status': self.status,
            'lead_source': self.lead_source,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


# =============================================================================
# Segment Model (Dynamic Customer Grouping)
# =============================================================================
class Segment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Criteria as JSON: {field: value, operator: 'eq'|'gt'|'lt'|'contains'}
    criteria = db.Column(db.Text, nullable=False)
    
    # Segment Type
    segment_type = db.Column(db.String(30), default='manual')  # manual, demographic, behavioral, purchase
    
    # Cached count (updated when segment is refreshed)
    customer_count = db.Column(db.Integer, default=0)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_criteria(self):
        return json.loads(self.criteria) if self.criteria else {}
    
    def set_criteria(self, data):
        self.criteria = json.dumps(data)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'criteria': self.get_criteria(),
            'segment_type': self.segment_type,
            'customer_count': self.customer_count,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


# =============================================================================
# Campaign Model (Multi-Channel Marketing)
# =============================================================================
class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Campaign Type
    campaign_type = db.Column(db.String(20), default='email')  # email, social, ads, sms
    
    # Content
    subject = db.Column(db.String(200), nullable=True)  # For email
    content = db.Column(db.Text, nullable=True)  # Message body/template
    
    # Targeting
    segment_id = db.Column(db.Integer, db.ForeignKey('segment.id'), nullable=False)
    
    # Scheduling
    status = db.Column(db.String(20), default='draft')  # draft, scheduled, active, paused, completed
    schedule_time = db.Column(db.DateTime, nullable=True)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    
    # Budget & Cost
    budget = db.Column(db.Float, default=0.0)
    cost_per_send = db.Column(db.Float, default=0.01)  # Simulated cost
    
    # Workflow automation
    workflow_steps = db.Column(db.Text, nullable=True)  # JSON array of automation steps
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    segment = db.relationship('Segment', backref=db.backref('campaigns', lazy=True))
    
    def get_workflow_steps(self):
        return json.loads(self.workflow_steps) if self.workflow_steps else []
    
    def set_workflow_steps(self, data):
        self.workflow_steps = json.dumps(data)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'campaign_type': self.campaign_type,
            'subject': self.subject,
            'content': self.content,
            'segment_id': self.segment_id,
            'segment_name': self.segment.name if self.segment else None,
            'status': self.status,
            'schedule_time': self.schedule_time.isoformat() if self.schedule_time else None,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'budget': self.budget,
            'cost_per_send': self.cost_per_send,
            'workflow_steps': self.get_workflow_steps(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


# =============================================================================
# Campaign Results (Marketing Analytics)
# =============================================================================
class CampaignResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    
    # Delivery Metrics
    total_sent = db.Column(db.Integer, default=0)
    delivered = db.Column(db.Integer, default=0)
    bounced = db.Column(db.Integer, default=0)
    
    # Engagement Metrics
    opens = db.Column(db.Integer, default=0)
    clicks = db.Column(db.Integer, default=0)
    unsubscribes = db.Column(db.Integer, default=0)
    
    # Legacy fields (keeping for compatibility)
    impressions = db.Column(db.Integer, default=0)
    
    # Conversion Metrics
    conversions = db.Column(db.Integer, default=0)
    leads_generated = db.Column(db.Integer, default=0)
    leads_converted = db.Column(db.Integer, default=0)
    
    # Revenue Attribution
    revenue_attributed = db.Column(db.Float, default=0.0)
    total_cost = db.Column(db.Float, default=0.0)
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    campaign = db.relationship('Campaign', backref=db.backref('results', uselist=False, lazy=True))
    
    def calculate_metrics(self):
        """Calculate derived metrics"""
        metrics = {
            'campaign_id': self.campaign_id,
            'total_sent': self.total_sent,
            'delivered': self.delivered,
            'bounced': self.bounced,
            'opens': self.opens,
            'clicks': self.clicks,
            'conversions': self.conversions,
            'leads_generated': self.leads_generated,
            'leads_converted': self.leads_converted,
            'revenue_attributed': self.revenue_attributed,
            'total_cost': self.total_cost,
            
            # Calculated Rates
            'delivery_rate': (self.delivered / self.total_sent * 100) if self.total_sent > 0 else 0,
            'open_rate': (self.opens / self.delivered * 100) if self.delivered > 0 else 0,
            'click_rate': (self.clicks / self.opens * 100) if self.opens > 0 else 0,
            'ctr': (self.clicks / self.delivered * 100) if self.delivered > 0 else 0,
            'conversion_rate': (self.conversions / self.clicks * 100) if self.clicks > 0 else 0,
            
            # ROI
            'roi': ((self.revenue_attributed - self.total_cost) / self.total_cost * 100) if self.total_cost > 0 else 0
        }
        return metrics
    
    def to_dict(self):
        return self.calculate_metrics()


# =============================================================================
# Segment-Customer Association (for tracking membership)
# =============================================================================
segment_customers = db.Table('segment_customers',
    db.Column('segment_id', db.Integer, db.ForeignKey('segment.id'), primary_key=True),
    db.Column('customer_id', db.Integer, db.ForeignKey('customer.id'), primary_key=True),
    db.Column('added_at', db.DateTime, default=datetime.utcnow)
)


# =============================================================================
# Campaign Activity Log (for analytics tracking)
# =============================================================================
class CampaignActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True)
    
    activity_type = db.Column(db.String(20), nullable=False)  # sent, opened, clicked, converted
    activity_data = db.Column(db.Text, nullable=True)  # JSON additional data
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    campaign = db.relationship('Campaign', backref=db.backref('activities', lazy=True))
    customer = db.relationship('Customer', backref=db.backref('campaign_activities', lazy=True))
