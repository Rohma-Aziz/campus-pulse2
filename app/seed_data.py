import pandas as pd
import random
from datetime import datetime, timedelta

departments = ['CSE', 'AIDS', 'ECE', 'ME', 'CE']
categories = ['Wi-Fi', 'Hostel', 'Cafe', 'Library', 'Classrooms', 'Cleanliness']

# Generate 100 sample feedback entries
data = []
for i in range(1, 101):
    dept = random.choice(departments)
    cat = random.choice(categories)
    
    # Simulate realistic lower ratings for AIDS Wi-Fi to test auto-insights
    if dept == 'AIDS' and cat == 'Wi-Fi':
        rating = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
    else:
        rating = random.choices([1, 2, 3, 4, 5], weights=[0.1, 0.1, 0.2, 0.3, 0.3])[0]
        
    date = datetime.today() - timedelta(days=random.randint(0, 90))
    data.append({
        'feedback_id': i,
        'department': dept,
        'category': cat,
        'rating': rating,
        'status': random.choice(['Pending', 'In Progress', 'Resolved']),
        'created_at': date
    })

df = pd.DataFrame(data)
df.to_csv('sample_feedback.csv', index=False)
print("Sample dataset created: sample_feedback.csv")