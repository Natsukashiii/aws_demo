# coding=UTF-8

from flask import Flask, render_template, request,jsonify,make_response
import boto3
from threading import Lock
from flask_socketio import SocketIO
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources=r'/*')

socketio = SocketIO(app)

file_name = None
snapshot_id = None
thread = None
thread_lock = Lock()
s3 = None
file_size = 1


@app.route("/", methods=['GET', 'POST'])
def awsDemo():
    print('Hello AWS!')
    print(boto3.__version__)
    return render_template('index.html')


# Section One
# 创建快照
@app.route("/createSnapshot", methods=['POST'])
def createSnapshot():
    print('start getting snapshot...')

    ec2 = boto3.client('ec2')
    try:
        snapshot = ec2.create_snapshot(VolumeId='vol-0dce1be62908cded4', Description='aws-demo-task1')

        # get snapshotid
        global snapshot_id
        snapshot_id = snapshot['SnapshotId']

        print("Created SnapShot Success!,", snapshot_id)

        res='<p>Created SnapShot Success!</p>' + 'snapshot_id: ' + snapshot_id

        response = make_response(jsonify(res))
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'OPTIONS,HEAD,GET,POST'
        response.headers['Access-Control-Allow-Headers'] = 'x-requested-with'

        return '<p>Created SnapShot Success!</p>' + 'snapshot_id: ' + snapshot_id
    except Exception as e:
        print("Created SnapShot Failed!")
        return 'Created SnapShot Failed!'


# 发送快照状态(websocket)
@socketio.on('connect', namespace="/getStatus")
def getCreateStatus():
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(target=getSnapState)


# 获取快照状态
def getSnapState():
    print('getSnapState')
    ec2 = boto3.resource('ec2')
    global snapshot_id
    while True:
        socketio.sleep(0.01)
        snapshot = ec2.Snapshot(snapshot_id)
        progress = snapshot.progress
        state = snapshot.state
        res = {'state': state, 'progress': progress}
        socketio.emit('server_response', {'data': res}, namespace='/getStatus')


if __name__ == '__main__':
    # CORS(app)
    socketio.run(app, host='0.0.0.0', port=5000)
    # CORS(socketio)
