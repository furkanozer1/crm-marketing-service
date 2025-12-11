from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from functools import wraps
import services
from models import db
from datetime import datetime
import json

marketing_bp = Blueprint('marketing', __name__)


# =============================================================================
# Authentication Decorator
# =============================================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('marketing.login_page'))
        return f(*args, **kwargs)
    return decorated_function


# =============================================================================
# Page Routes (Frontend)
# =============================================================================
@marketing_bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('marketing.dashboard_page'))
    return redirect(url_for('marketing.login_page'))


@marketing_bp.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect(url_for('marketing.dashboard_page'))
    return render_template('login.html')


@marketing_bp.route('/dashboard')
@login_required
def dashboard_page():
    return render_template('dashboard.html')


@marketing_bp.route('/segments-page')
@login_required
def segments_page():
    return render_template('segments.html')


@marketing_bp.route('/campaigns-page')
@login_required
def campaigns_page():
    return render_template('campaigns.html')


@marketing_bp.route('/analytics-page')
@login_required
def analytics_page():
    return render_template('analytics.html')


@marketing_bp.route('/customers-page')
@login_required
def customers_page():
    return render_template('customers.html')


# =============================================================================
# Authentication API
# =============================================================================
@marketing_bp.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Missing username or password'}), 400
    
    user = services.authenticate_user(data['username'], data['password'])
    if user:
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict()
        }), 200
    
    return jsonify({'error': 'Invalid credentials'}), 401


@marketing_bp.route('/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200


@marketing_bp.route('/auth/me', methods=['GET'])
@login_required
def get_current_user():
    user = services.get_user_by_id(session['user_id'])
    if user:
        return jsonify(user.to_dict()), 200
    return jsonify({'error': 'User not found'}), 404


# =============================================================================
# Customer API
# =============================================================================
@marketing_bp.route('/customers', methods=['GET'])
@login_required
def list_customers():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    search = request.args.get('search')
    
    pagination = services.get_all_customers(page, per_page, status, search)
    
    return jsonify({
        'customers': [c.to_dict() for c in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page
    }), 200


@marketing_bp.route('/customers/<int:id>', methods=['GET'])
@login_required
def get_customer(id):
    customer = services.get_customer_by_id(id)
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404
    return jsonify(customer.to_dict()), 200


@marketing_bp.route('/customers', methods=['POST'])
@login_required
def create_customer():
    data = request.get_json()
    if not data or 'name' not in data or 'email' not in data:
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        customer = services.create_customer(
            name=data['name'],
            email=data['email'],
            phone=data.get('phone'),
            demographics=data.get('demographics'),
            status=data.get('status', 'lead'),
            lead_source=data.get('lead_source')
        )
        return jsonify(customer.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@marketing_bp.route('/customers/<int:id>', methods=['PUT'])
@login_required
def update_customer(id):
    data = request.get_json()
    customer = services.update_customer(id, **data)
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404
    return jsonify(customer.to_dict()), 200


# =============================================================================
# Segment API
# =============================================================================
@marketing_bp.route('/segments', methods=['POST'])
@login_required
def create_segment():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'Missing segment name'}), 400
    
    criteria = data.get('criteria', {})
    if isinstance(criteria, str):
        criteria = {'rules': [], 'match': 'all', 'description': criteria}
    
    segment = services.create_segment(
        name=data['name'],
        criteria=criteria,
        description=data.get('description'),
        segment_type=data.get('segment_type', 'manual')
    )
    return jsonify(segment.to_dict()), 201


@marketing_bp.route('/segments', methods=['GET'])
@login_required
def list_segments():
    segments = services.get_all_segments()
    return jsonify([s.to_dict() for s in segments]), 200


@marketing_bp.route('/segments/<int:id>', methods=['GET'])
@login_required
def get_segment(id):
    segment = services.get_segment_by_id(id)
    if not segment:
        return jsonify({'error': 'Segment not found'}), 404
    return jsonify(segment.to_dict()), 200


@marketing_bp.route('/segments/<int:id>', methods=['PUT'])
@login_required
def update_segment(id):
    data = request.get_json()
    segment = services.update_segment(id, **data)
    if not segment:
        return jsonify({'error': 'Segment not found'}), 404
    return jsonify(segment.to_dict()), 200


@marketing_bp.route('/segments/<int:id>/customers', methods=['GET'])
@login_required
def get_segment_customers(id):
    customers = services.get_segment_customers(id)
    return jsonify({
        'segment_id': id,
        'count': len(customers),
        'customers': [c.to_dict() for c in customers[:100]]  # Limit to 100
    }), 200


@marketing_bp.route('/segments/<int:id>/refresh', methods=['POST'])
@login_required
def refresh_segment(id):
    segment = services.refresh_segment(id)
    if not segment:
        return jsonify({'error': 'Segment not found'}), 404
    return jsonify(segment.to_dict()), 200


# =============================================================================
# Campaign API
# =============================================================================
@marketing_bp.route('/campaigns', methods=['POST'])
@login_required
def create_campaign():
    data = request.get_json()
    if not data or 'name' not in data or 'segment_id' not in data:
        return jsonify({'error': 'Missing name or segment_id'}), 400
    
    schedule_time = None
    if 'schedule_time' in data and data['schedule_time']:
        try:
            schedule_time = datetime.fromisoformat(data['schedule_time'])
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use ISO 8601'}), 400

    try:
        campaign = services.create_campaign(
            name=data['name'],
            segment_id=data['segment_id'],
            campaign_type=data.get('campaign_type', 'email'),
            subject=data.get('subject'),
            content=data.get('content'),
            schedule_time=schedule_time,
            budget=data.get('budget', 0.0),
            description=data.get('description')
        )
        return jsonify(campaign.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@marketing_bp.route('/campaigns', methods=['GET'])
@login_required
def list_campaigns():
    status = request.args.get('status')
    campaigns = services.get_all_campaigns(status)
    return jsonify([c.to_dict() for c in campaigns]), 200


@marketing_bp.route('/campaigns/<int:id>', methods=['GET'])
@login_required
def get_campaign(id):
    campaign = services.get_campaign_by_id(id)
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404
    return jsonify(campaign.to_dict()), 200


@marketing_bp.route('/campaigns/<int:id>', methods=['PUT'])
@login_required
def update_campaign(id):
    data = request.get_json()
    campaign = services.update_campaign(id, **data)
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404
    return jsonify(campaign.to_dict()), 200


@marketing_bp.route('/campaigns/<int:id>/launch', methods=['POST'])
@login_required
def launch_campaign(id):
    campaign = services.launch_campaign(id)
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404
    return jsonify(campaign.to_dict()), 200


@marketing_bp.route('/campaigns/<int:id>/resume', methods=['POST'])
@login_required
def resume_campaign(id):
    campaign = services.resume_campaign(id)
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404
    return jsonify(campaign.to_dict()), 200


@marketing_bp.route('/campaigns/<int:id>/pause', methods=['POST'])
@login_required
def pause_campaign(id):
    campaign = services.pause_campaign(id)
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404
    return jsonify(campaign.to_dict()), 200


@marketing_bp.route('/campaigns/<int:id>/complete', methods=['POST'])
@login_required
def complete_campaign(id):
    campaign = services.complete_campaign(id)
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404
    return jsonify(campaign.to_dict()), 200


@marketing_bp.route('/campaigns/<int:id>/stats', methods=['GET'])
@login_required
def get_stats(id):
    stats = services.get_campaign_stats(id)
    if not stats:
        return jsonify({'error': 'Campaign or stats not found'}), 404
    return jsonify(stats), 200


# =============================================================================
# Analytics API
# =============================================================================
@marketing_bp.route('/analytics/overview', methods=['GET'])
@login_required
def get_analytics_overview():
    overview = services.get_analytics_overview()
    return jsonify(overview), 200


@marketing_bp.route('/analytics/roi', methods=['GET'])
@login_required
def get_roi_report():
    report = services.get_campaign_roi_report()
    return jsonify({'campaigns': report}), 200


@marketing_bp.route('/analytics/funnel', methods=['GET'])
@login_required
def get_funnel():
    funnel = services.get_conversion_funnel()
    return jsonify(funnel), 200


@marketing_bp.route('/analytics/segments', methods=['GET'])
@login_required
def get_segment_performance():
    performance = services.get_segment_performance()
    return jsonify({'segments': performance}), 200


# =============================================================================
# Demo Data API
# =============================================================================
@marketing_bp.route('/demo/initialize', methods=['POST'])
def initialize_demo():
    """Initialize demo data - no auth required for first setup"""
    result = services.initialize_demo_data()
    if result:
        return jsonify({'message': 'Demo data initialized successfully'}), 201
    return jsonify({'message': 'Demo data already exists'}), 200
