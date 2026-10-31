"""The words and numbers of the demo data, kept apart from the code that saves them.

Prices are in taka. Day offsets are relative to "now", so a demo database always has events coming up,
one on right now, and some finished ones to review.
"""

PASSWORD = 'demo12345'
ADMIN_PASSWORD = 'admin12345'

# username, first name, last name, role, phone, bio
PEOPLE = [
    ('admin', 'Site', 'Admin', 'admin', '01700000001', 'Looks after EventEase.'),
    ('rafiq_events', 'Rafiq', 'Hasan', 'event_manager', '01711000002', 'Runs concerts and festivals across Dhaka.'),
    ('nusrat_org', 'Nusrat', 'Jahan', 'event_manager', '01711000003', 'Corporate events, workshops and expos.'),
    ('tanvir_venues', 'Tanvir', 'Ahmed', 'venue_manager', '01811000004', 'Manages three halls in Dhaka and Rajshahi.'),
    ('shirin_hall', 'Shirin', 'Akter', 'venue_manager', '01811000005', 'Manages venues in Dhaka, Sylhet and Chattogram.'),
    ('ayesha', 'Ayesha', 'Rahman', 'basic_user', '01911000006', 'Festival goer. Always up for live music.'),
    ('mim', 'Mim', 'Chowdhury', 'basic_user', '01911000007', 'Photographer and weekend traveller.'),
    ('sabbir', 'Sabbir', 'Khan', 'basic_user', '01911000008', 'Software engineer. Tech talks and cricket.'),
    ('tasnia', 'Tasnia', 'Islam', 'basic_user', '01911000009', 'Wants to start organising events.'),
    ('kamal', 'Kamal', 'Hossain', 'basic_user', '01911000010', 'Runs a small catering business.'),
    ('farhan', 'Farhan', 'Sheikh', 'basic_user', '01911000011', 'Music student.'),
    ('nabila', 'Nabila', 'Karim', 'basic_user', '01911000012', 'Product designer.'),
    ('rubel', 'Rubel', 'Mia', 'basic_user', '01911000013', 'Marathon runner.'),
    ('sadia', 'Sadia', 'Afrin', 'basic_user', '01911000014', 'Planning a wedding next year.'),
    ('newbie', 'New', 'Member', 'basic_user', '01911000015', ''),
]

# key, name, type, city, state, zipcode, capacity, per hour, per day, amenities, manager, description
VENUES = [
    ('ballroom', 'Grand Ballroom Gulshan', 'banquet_hall', 'Dhaka', 'Dhaka', '1212', 800, 12000, 90000,
     ('parking', 'wifi', 'catering', 'av', 'ac', 'access'), 'tanvir_venues',
     'A pillar-free ballroom with a stage, a bridal suite and a full catering kitchen. Suited to weddings, galas and large corporate dinners.'),
    ('lakeview', 'Lakeview Conference Center', 'conference_hall', 'Dhaka', 'Dhaka', '1213', 300, 6000, 45000,
     ('parking', 'wifi', 'av', 'ac', 'access'), 'tanvir_venues',
     'Three breakout rooms and a 300-seat main hall overlooking the lake. Projectors, microphones and fibre internet are included.'),
    ('arena', 'Riverside Open Arena', 'outdoor_space', 'Sylhet', 'Sylhet', '3100', 2500, 9000, 70000,
     ('parking', 'access'), 'shirin_hall',
     'A walled riverside lawn for concerts and fairs, with a covered stage, floodlights and room for food stalls.'),
    ('rooftop', 'The Rooftop Lounge', 'restaurant', 'Dhaka', 'Dhaka', '1213', 120, 4500, 32000,
     ('wifi', 'catering', 'ac'), 'shirin_hall',
     'A rooftop restaurant with skyline views, a small stage and a bar. Good for launches, birthdays and acoustic nights.'),
    ('auditorium', 'National Cultural Auditorium', 'auditorium', 'Chattogram', 'Chattogram', '4000', 1000, 8000, 60000,
     ('parking', 'av', 'ac', 'access'), 'shirin_hall',
     'A tiered 1,000-seat auditorium with professional lighting and sound, dressing rooms and a green room.'),
    ('sports', 'Green Field Sports Complex', 'sports_facility', 'Rajshahi', 'Rajshahi', '6000', 1500, 5000, 38000,
     ('parking', 'access'), 'tanvir_venues',
     'A turf ground, two indoor courts and changing rooms. Floodlit for evening matches and fun runs.'),
]

# key, title, type, venue key (or None), days from now, hours long, max, price, free, tiers, palette, description
# tiers: (name, category_type, price, quantity)
EVENTS = [
    ('jazz', 'Dhaka Jazz Night', 'concert', 'ballroom', 12, 4, 400, 500, False,
     [('General', 'general', 500, 250), ('VIP', 'vip', 1500, 40), ('Early Bird', 'early_bird', 350, 60)], 0,
     'An evening of live jazz with four bands, from standards to fusion. Doors open at 6, first set at 7. Light snacks are included with VIP.'),
    ('summit', 'Startup Founders Summit', 'conference', 'lakeview', 20, 8, 250, 2000, False,
     [('Student', 'student', 800, 80), ('General', 'general', 2000, 170)], 1,
     'A day of talks and workshops for founders at every stage: funding, hiring, product and growth, with a networking lunch.'),
    ('openmic', 'Open Mic Evening', 'party', 'rooftop', 5, 3, 80, 0, True, [], 2,
     'Sing, read, play or just listen. Sign up at the door for a five minute slot. Free entry, tea and snacks on sale.'),
    ('photo', 'Street Photography Workshop', 'workshop', None, 9, 5, 8, 1200, False, [], 3,
     'A hands-on walk and critique session in Old Dhaka with a working photographer. Bring any camera. Small group, so only 8 places.'),
    ('rockfest', 'Rock Fest Sylhet', 'festival', 'arena', 15, 7, 6, 900, False, [], 6,
     'Local rock bands on the riverside lawn. A small, sold-out launch edition: join the waiting list on the event page.'),
    ('run', 'Charity Fun Run 5K', 'sports', 'sports', 30, 3, 500, 0, True, [], 3,
     'A 5K fun run through the sports complex grounds to raise money for school libraries. Medals for all finishers.'),
    ('art', 'Winter Art Exhibition', 'exhibition', 'auditorium', 40, 72, 600, 0, True, [], 4,
     'Paintings, prints and sculpture from thirty emerging artists. Free entry, open daily for three days.'),
    ('talk', 'Tech Talk: Django at Scale', 'seminar', 'lakeview', 3, 2, 120, 0, True, [], 5,
     'Two engineers share how they grew a Django application to millions of requests a day. Q and A after. Registration closes soon.'),
    ('bookfair', 'Book Fair Weekend', 'exhibition', 'ballroom', -1, 72, 2000, 100, False, [], 7,
     'Three days of publishers, signings and children\'s corners. This edition is on right now.'),
    ('eid', 'Eid Music Festival', 'festival', 'arena', -30, 8, 1500, 700, False, [], 0,
     'A day-long Eid celebration with folk, pop and rock acts.'),
    ('leadership', 'Corporate Leadership Workshop', 'workshop', 'lakeview', -14, 7, 80, 3000, False, [], 1,
     'A one-day intensive on leading hybrid teams, with case studies and group exercises.'),
    ('expo', 'Wedding Expo 2026', 'exhibition', 'ballroom', -50, 10, 800, 0, True, [], 5,
     'Over eighty vendors: venues, caterers, photographers and designers.'),
]

# (title, author, days ago, paragraphs, image count, has file)
# The hour each event starts, so the times read like real ones: a fun run at dawn, a gig after work.
# Anything missing falls back to 7 pm.
START_HOURS = {
    'jazz': 18, 'summit': 9, 'openmic': 19, 'photo': 15, 'rockfest': 16, 'run': 7,
    'art': 10, 'talk': 18, 'bookfair': 10, 'eid': 12, 'leadership': 9, 'expo': 10,
}

BLOG_POSTS = [
    ('How we ran Dhaka Jazz Night without a single queue', 'rafiq_events', 6,
     ['Three weeks before doors opened we moved to numbered tickets and a two-lane entrance, and it changed everything.',
      'Here is the short version of what worked: tickets scanned on a phone, a separate lane for VIP, and a volunteer whose only job was to answer "where do I go?".',
      'The biggest surprise was how much a clear schedule on the website reduced calls. Put the set times up early.'], 3, True),
    ('Five tips for your first festival', 'ayesha', 4,
     ['Pack light and wear shoes you can stand in for six hours.',
      'Charge your phone before you leave and agree a meeting point with friends, because signal drops once the crowd arrives.',
      'Drink water, eat before the headliner, and stay for the last song. Most people leave early and miss the best part.'], 2, False),
    ('A venue-hunting checklist for organisers', 'tanvir_venues', 10,
     ['Visit at the time of day your event will run, not at noon on a quiet weekday.',
      'Ask three questions: what is included in the hourly price, what is the cancellation window, and who is on site on the day.',
      'Check the loading route for equipment, and count the power sockets.'], 1, True),
    ('Behind the scenes at Wedding Expo 2026', 'nusrat_org', 20,
     ['Eighty vendors, one hall, and a build window of nine hours. This is how the floor plan came together.',
      'We started with traffic flow, put the busiest stalls at the far end so visitors walk past everything, and left space for the photographers to breathe.'], 2, False),
]

SITE_REVIEWS = [
    ('ayesha', 5, 'Booked in two minutes', 'Found a jazz night, picked VIP tickets, paid with bKash and had the confirmation straight away.', True),
    ('mim', 5, 'Easy for a first-timer', 'Everything I needed was on one page: date, venue, price and a map. No surprises.', False),
    ('sabbir', 4, 'Great for tech events', 'I follow the tech talks here. Reminders could arrive a little earlier, but otherwise perfect.', False),
    ('rafiq_events', 5, 'Our go-to for ticketing', 'The organiser dashboard shows exactly who has paid and how much we have made. Saved us a spreadsheet.', True),
    ('tanvir_venues', 4, 'More bookings for our halls', 'Requests arrive with the date, the event and the contact already filled in. Approving is one tap.', False),
    ('kamal', 3, 'Good, wants more filters', 'Search works well. I would love a map view and a price slider.', False),
]

EVENT_REVIEWS = {
    'eid': [
        ('ayesha', 5, 5, 4, 4, 'Best Eid ever', 'The line-up was superb and the lawn stayed clean all day. Food stalls were a little pricey.'),
        ('mim', 4, 4, 4, 3, 'Great music, long queues', 'Loved the folk set. Entry was slow at the start but moved fast after 4 pm.'),
        ('sabbir', 5, 5, 5, 4, 'Worth it', 'Sound was clear even at the back. Would go again.'),
    ],
    'leadership': [
        ('kamal', 4, 5, 4, 3, 'Practical and well paced', 'The case studies were the highlight. Lunch ran late.'),
        ('nabila', 5, 5, 4, 4, 'Left with a plan', 'Clear takeaways I could use on Monday morning.'),
    ],
    'expo': [
        ('ayesha', 4, 4, 5, 5, 'Plenty to see', 'Spent four hours and still missed some stalls. Free entry made it easy.'),
        ('sadia', 5, 5, 5, 5, 'Found our photographer', 'Met three photographers in an hour and booked one the same day.'),
    ],
}

# venue key, user, days ago the booking ended, hours, title, ratings (overall, ambience, service, clean, value), title, comment
VENUE_REVIEWS = [
    ('lakeview', 'ayesha', 'Book club annual meet', (5, 5, 5, 5, 4), 'Bright and well kept', 'Spotless rooms and the AV worked first time.'),
    ('ballroom', 'kamal', 'Family wedding reception', (4, 5, 4, 4, 3), 'Beautiful hall', 'Gorgeous space. Parking got tight with 400 guests.'),
    ('rooftop', 'farhan', 'Acoustic launch party', (5, 5, 5, 4, 5), 'Great views', 'Staff were quick and the sunset made the night.'),
    ('auditorium', 'nabila', 'Design school showcase', (4, 4, 4, 5, 4), 'Professional setup', 'Sound and lights are proper theatre grade.'),
    ('arena', 'rafiq_events', 'Spring open-air concert', (5, 5, 4, 4, 5), 'Ideal for crowds', 'Plenty of room, easy load-in for the stage crew.'),
]
