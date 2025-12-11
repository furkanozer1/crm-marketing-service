from app import create_app, db
app = create_app()
from models import Campaign, Segment
import services
from datetime import datetime

def test_launch():
    with app.app_context():
        # Setup: Ensure a draft campaign exists
        campaign_name = f'Test Campaign Large {datetime.now().timestamp()}'
        campaign = services.create_campaign(
             name=campaign_name,
             # Create a new segment with impossible criteria to ensure it has 0 customers
             # effectively triggering the 'random.randint(100, 500)' simulation fallback
             segment_id=services.create_segment('Test Seg Empty', {'rules': [{'field':'id', 'operator':'eq', 'value':-1}], 'match': 'all'}).id,
             campaign_type='email',
             budget=1000.0
        )
        
        # RESET STATE TO DRAFT FOR TEST
        campaign.status = 'draft'
        db.session.commit()
        print(f"Campaign {campaign.id} reset to draft.")
        
        # Test 1: Launch
        print("\n--- Testing Launch ---")
        try:
            c = services.launch_campaign(campaign.id)
            print(f"Launch success. Status: {c.status}")
            print(f"Start date: {c.start_date}")
            print(f"Results: {c.results.to_dict() if c.results else 'None'}")
        except Exception as e:
            print(f"Launch failed: {e}")
            import traceback
            traceback.print_exc()

        # Test 2: Pause
        print("\n--- Testing Pause ---")
        try:
            c = services.pause_campaign(campaign.id)
            print(f"Pause success. Status: {c.status}")
        except Exception as e:
            print(f"Pause failed: {e}")

        # Test 3: Resume (New API)
        print("\n--- Testing Resume (New API) ---")
        try:
            c = services.resume_campaign(campaign.id)
            print(f"Resume success. Status: {c.status}")
            print(f"Results: {c.results.to_dict() if c.results else 'None'}")
        except Exception as e:
            print(f"Resume failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    test_launch()
