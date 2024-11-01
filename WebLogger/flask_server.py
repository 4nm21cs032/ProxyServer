import os
import socket
from flask import Flask, request, render_template,jsonify
from flask_socketio import SocketIO, emit
import datetime 

app = Flask(__name__)
socketio = SocketIO(app)

logs = []
IP_FILE_PATH = os.path.join(os.path.dirname(__file__), '..', 'ProxyServer', 'blocked_ips.txt')
dns_entries={}

@app.route('/log', methods=['POST'])
def log():
    raw_log = request.form.get('log')
    if raw_log:
        log_entry = parse_log(raw_log)
        if log_entry['header'] == 'Added':
            logs.append(log_entry)
        elif log_entry['header'] == 'Removed':
            logs[:] = [log for log in logs if log['url'] != log_entry['url']]
        socketio.emit('update_log', log_entry)
    return 'Log received', 200

def parse_log(raw_log):
    print(raw_log)
    lines = raw_log.split('\n')
    log_entry = {
        'header': lines[0],
        'url': '',
        'data': '',
        'length': '',
        'lru_time_track': '',
        'server': '',
        'date': '',
        'content_type': '',
        'content_length': '',
        'location': '',
        'x_cache': ''
    }
    total_seconds=0
    for line in lines[1:]:
        if line.startswith('URL:'):
            log_entry['url'] = line.split(': ', 1)[1]
        elif line.startswith('Data:'):
            log_entry['data'] = line.split(': ', 1)[1]
        elif line.startswith('Length:'):
            log_entry['length'] = line.split(': ', 1)[1]
        elif line.startswith('Date:'):
            log_entry['date'] = line.split(': ', 1)[1]    
            time_str=log_entry['date']
            time_part = time_str.split(' ')
            time_t=time_part[4]
            hours, minutes, seconds = map(int, time_t.split(':'))
            print("hours:",type(hours))
            print("minutes:",type(minutes))
            print("seconds:",type(seconds))
            total_seconds += hours * 3600 + minutes * 60 + seconds            
           
        elif line.startswith('LRU Time Track:'):
            log_entry['lru_time_track'] = line.split(': ', 1)[1]  
            # time_str = line.split(': ', 1)[1]
            # time_str=int(time_str)
            # response_time=time_str-total_seconds
            # log_entry['lru_time_track'] = response_time
            # try:
            #     time_float = float(time_str)
            #     dt_object = datetime.datetime.fromtimestamp(time_float)
            #     formatted_time = dt_object.strftime("%Y-%m-%d %H:%M:%S")
            #     log_entry['lru_time_track'] = formatted_time
            # except ValueError:
            #     log_entry['lru_time_track'] = 'Error!'
        elif line.startswith('Server:'):
            log_entry['server'] = line.split(': ', 1)[1]
        
        elif line.startswith('Content-Type:'):
            log_entry['content_type'] = line.split(': ', 1)[1]
        elif line.startswith('Content-Length:'):
            log_entry['content_length'] = line.split(': ', 1)[1]
        elif line.startswith('Location:'):
            log_entry['location'] = line.split(': ', 1)[1]
    return log_entry

def get_ip_from_domain(dm):
    try:
        ip_address = socket.gethostbyname(dm)
        return ip_address
    except socket.gaierror:
        return "error"

@app.route('/get_blocked_ips')
def get_blocked_ips():
    blocked_ips = []
    try:
        with open(IP_FILE_PATH, 'r') as f:
            ips = f.readlines()
            for ip in ips:
                ip = ip.strip()
                domain = dns_entries.get(ip,"Unknown")
                blocked_ips.append({"ip": ip,"domain": domain})
    except FileNotFoundError:
        pass
    return jsonify(blocked_ips)


@app.route('/unblock', methods=['POST'])
def unblock_ip():
    ip_to_unblock = request.form.get('ip')
    try:
        with open(IP_FILE_PATH, 'r') as f:
            ips = f.readlines()
        
        with open(IP_FILE_PATH, 'w') as f:
            for ip in ips:
                if ip.strip() != ip_to_unblock:
                    f.write(ip)
        
        if ip_to_unblock in dns_entries:
            del dns_entries[ip_to_unblock]
            
        socketio.emit('unblock_ip', {'ip': ip_to_unblock})
        return jsonify({"message": f"IP {ip_to_unblock} has been unblocked successfully!"})
    except Exception as e:
        return jsonify({"error": f"An error occurred while unblocking the IP: {e}"})
    
@app.route('/')
def index():
    return render_template('weblogger.html', logs=logs)

@app.route('/get_logs')
def get_logs():
    return jsonify(logs)

@app.route('/block', methods=['GET', 'POST'])
def block_site():
    if request.method == 'POST':
        domain_name = request.form.get('ip')
        ip_address=get_ip_from_domain(domain_name)
        if ip_address=="error":
            return jsonify({"error": f"An error occurred while blocking the IP"})
        try:
            with open(IP_FILE_PATH,'a') as f:
                f.write(f"{ip_address}\n")
            dns_entries[ip_address]=domain_name
            socketio.emit('block_ip',{'ip':ip_address})
            return jsonify({"message": f"IP {ip_address} has been blocked successfully!"})
        except Exception as e:
            return jsonify({"error":f"An error occurred while blocking the IP:{e}"})
    return render_template('blockip.html')

if __name__ == '__main__':
    socketio.run(app, debug=True)
