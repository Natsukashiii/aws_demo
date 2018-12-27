# coding=UTF-8

from flask import Flask, render_template, request, make_response, jsonify
import boto3,datetime
from threading import Lock
from flask_socketio import SocketIO
from flask_cors import CORS

app = Flask(__name__)

socketio = SocketIO(app)
CORS(app)

file_name = None
snapshot_id = None
thread = None
thread_lock = Lock()
s3 = None
file_size = 1


@app.route("/", methods=['GET', 'POST'])
def awsDemo():
    print('Hello AWS!')
    return render_template('index.html')


# Section One
# 创建快照
@app.route("/createSnapshot", methods=['POST'])
def createSnapshot():
    print('start getting snapshot...',(datetime.datetime.now() + datetime.timedelta(seconds=10)).strftime('%Y-%m-%d %H:%M:%S'))
    ec2 = boto3.client('ec2')
    try:
        snapshot = ec2.create_snapshot(VolumeId='vol-01045394fbfb112b8', Description='aws-demo-task1')

        # get snapshotid
        global snapshot_id
        snapshot_id = snapshot['SnapshotId']
        global COMPLETE
        COMPLETE = False
        getCreateStatus()

        print("Created SnapShot Success!,", snapshot_id)
        print("Finished at",(datetime.datetime.now() + datetime.timedelta(seconds=10)).strftime('%Y-%m-%d %H:%M:%S'))
        return '<p>Created SnapShot Success!</p>' + 'snapshot_id: ' + snapshot_id
    except Exception as e:
        print(e)
        print("Created SnapShot Failed!")
        return 'Created SnapShot Failed!'

@app.route("/complete", methods=['GET'])
def complete():
    global COMPLETE
    COMPLETE = True
    global thread
    thread = None
    print("Complete>>>>>>>>>>>")
    return "complete"

# 发送快照状态(websocket)
# @socketio.on('connect', namespace="/getStatus")
def getCreateStatus():
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(target=getSnapState)


# 获取快照状态
def getSnapState():
    print('getSnapState'+ (datetime.datetime.now() + datetime.timedelta(seconds=10)).strftime('%Y-%m-%d %H:%M:%S'))
    ec2 = boto3.resource('ec2')
    global snapshot_id
    global COMPLETE
    while True and not COMPLETE:
        print("Send progress to client >>> ",  (datetime.datetime.now() + datetime.timedelta(seconds=10)).strftime('%Y-%m-%d %H:%M:%S'))
        socketio.sleep(0.01)
        snapshot = ec2.Snapshot(snapshot_id)
        progress = snapshot.progress
        state = snapshot.state
        res = {'state': state, 'progress': progress}
        socketio.emit('server_response', {'data': res}, namespace='/getStatus')



if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
