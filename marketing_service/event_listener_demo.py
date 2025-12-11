import redis
import json
import time
from datetime import datetime

def listen_to_events():
    print("\n🎧 [Subscriber Demo] Connecting to Event Bus (Redis)...")
    try:
        r = redis.from_url('redis://localhost:6379/0')
        pubsub = r.pubsub()
        pubsub.subscribe('crm_events')
        
        print("✅ [Subscriber Demo] Listening for events on channel 'crm_events'...")
        print("   (Press Ctrl+C to stop)")
        
        for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    event_type = data.get('event', 'Unknown')
                    timestamp = data.get('timestamp', '')
                    
                    print(f"\n📨 [Event Received] {event_type} at {timestamp}")
                    print(json.dumps(data['data'], indent=4))
                    
                except json.JSONDecodeError:
                    print(f"Received raw message: {message['data']}")
            
            # Keep the loop responsive
            time.sleep(0.01)
            
    except redis.ConnectionError:
        print("❌ [Error] Could not connect to Redis. Is it running?")
    except KeyboardInterrupt:
        print("\n👋 Stopping listener...")

if __name__ == "__main__":
    listen_to_events()
