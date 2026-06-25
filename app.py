from flask import Flask, render_template, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import string
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app, async_mode='eventlet')

# Store room state:
# {
#   'room_id': {
#       'current_video': None,
#       'is_playing': False,
#       'timestamp': 0,
#       'queue': []  # List of video IDs
#   }
# }
rooms = {}

def generate_room_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create')
def create_room():
    room_id = generate_room_id()
    while room_id in rooms:
        room_id = generate_room_id()
    
    rooms[room_id] = {
        'current_video': None,
        'is_playing': False,
        'timestamp': 0,
        'queue': []
    }
    return redirect(url_for('room', room_id=room_id))

@app.route('/room/<room_id>')
def room(room_id):
    if room_id not in rooms:
        # Initialize if accessed directly (or redirect to home)
        rooms[room_id] = {
            'current_video': None,
            'is_playing': False,
            'timestamp': 0,
            'queue': []
        }
    return render_template('room.html', room_id=room_id)

@socketio.on('join')
def on_join(data):
    room_id = data['room_id']
    join_room(room_id)
    if room_id in rooms:
        # Send current state to the joining user
        emit('init_state', rooms[room_id], room=room_id) # Using room=room_id to ensure targeting but really only need to reply to sender? 
        # Actually emit to sender only for init is better usually, or we can just broadcast update.
        # But 'init_state' should probably be just for the user.
        # However, emit() by default sends to the requestor context if 'room' isn't specified, but inside a namespace context it might differ.
        # Let's simple emit back to sender.
        emit('init_state', rooms[room_id])

@socketio.on('sync_action')
def on_sync_action(data):
    room_id = data['room_id']
    if room_id in rooms:
        # Update server state
        if 'action' in data:
            if data['action'] == 'play':
                rooms[room_id]['is_playing'] = True
            elif data['action'] == 'pause':
                rooms[room_id]['is_playing'] = False
        
        if 'timestamp' in data:
            rooms[room_id]['timestamp'] = data['timestamp']
            
        # Broadcast to others
        emit('sync_action', data, room=room_id, include_self=False)

@socketio.on('add_to_queue')
def on_add_to_queue(data):
    room_id = data['room_id']
    video_id = data['video_id']
    if room_id in rooms:
        rooms[room_id]['queue'].append(video_id)
        # Broadcast updated queue
        emit('update_queue', rooms[room_id]['queue'], room=room_id)
        
        # If nothing is playing, play this immediately?
        # Or let user decide. Let's just update queue.
        if rooms[room_id]['current_video'] is None:
             # Auto-play if empty
             play_next_video(room_id)

@socketio.on('play_next')
def on_play_next(data):
    room_id = data['room_id']
    play_next_video(room_id)

def play_next_video(room_id):
    if room_id in rooms and rooms[room_id]['queue']:
        next_video = rooms[room_id]['queue'].pop(0)
        rooms[room_id]['current_video'] = next_video
        rooms[room_id]['is_playing'] = True
        rooms[room_id]['timestamp'] = 0
        
        # Broadcast new video and queue update
        emit('change_video', {'video_id': next_video}, room=room_id)
        emit('update_queue', rooms[room_id]['queue'], room=room_id)
    elif room_id in rooms:
         # Queue empty
         pass

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)
