#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Basic Dahua RPC wrapper.
Forked from https://gist.github.com/48072a72be3a169bc43549e676713201.git
Added ANPR Plate Number extraction by Naveen Sakthivel <https://github.com/naveenrobo>
Example:
    from dahua_rpc import DahuaRpc
    dahua = DahuaRpc(host="192.168.1.10", username="admin", password="password")
    dahua.login()
  # Get the current time on the device
    print(dahua.current_time())
  # Set display to 4 grids with first view group
    dahua.set_split(mode=4, view=1)
  # Make a raw RPC request to get serial number
    print(dahua.request(method="magicBox.getSerialNo"))
  # Get the ANPR Plate Numbers by using the following
    object_id = dahua.get_traffic_info() # Get the object id
    dahua.startFind(object_id=object_id) # Use the object id to find the Plate Numbers
    response = json.dumps(dahua.do_find(object_id=object_id)) # Extract the Plate Numbers
Dependencies:
  pip install requests
"""

import sys
import hashlib
import requests
import time
from enum import Enum

if (sys.version_info > (3, 0)):
    unicode = str


class DahuaRpc(object):

    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password

        self.s = requests.Session()
        self.session_id = None
        self.id = 0

    def request(self, method, params=None, object_id=None, extra=None, url=None):
        """Make a RPC request."""
        self.id += 1
        data = {'method': method, 'id': self.id}
        if params is not None:
            data['params'] = params
        if object_id:
            data['object'] = object_id
        if extra is not None:
            data.update(extra)
        if self.session_id:
            data['session'] = self.session_id
        if not url:
            url = "http://{}/RPC2".format(self.host)
        r = self.s.post(url, json=data)
        return r.json()

    def login(self):
        """Dahua RPC login.
        Reversed from rpcCore.js (login, getAuth & getAuthByType functions).
        Also referenced:
        https://gist.github.com/avelardi/1338d9d7be0344ab7f4280618930cd0d
        """

        # login1: get session, realm & random for real login
        url = 'http://{}/RPC2_Login'.format(self.host)
        method = "global.login"
        params = {'userName': self.username,
                  'password': "",
                  'clientType': "Web3.0"}
        r = self.request(method=method, params=params, url=url)

        self.session_id = r['session']
        realm = r['params']['realm']
        random = r['params']['random']

        # Password encryption algorithm
        # Reversed from rpcCore.getAuthByType
        pwd_phrase = self.username + ":" + realm + ":" + self.password
        if isinstance(pwd_phrase, unicode):
            pwd_phrase = pwd_phrase.encode('utf-8')
        pwd_hash = hashlib.md5(pwd_phrase).hexdigest().upper()
        pass_phrase = self.username + ':' + random + ':' + pwd_hash
        if isinstance(pass_phrase, unicode):
            pass_phrase = pass_phrase.encode('utf-8')
        pass_hash = hashlib.md5(pass_phrase).hexdigest().upper()

        # login2: the real login
        params = {'userName': self.username,
                  'password': pass_hash,
                  'clientType': "Web3.0",
                  'authorityType': "Default",
                  'passwordType': "Default"}
        r = self.request(method=method, params=params, url=url)
        
        print(f"Login obtenido: {r}")
        
        # Use the correct session id from the second login request
        if r["result"] is True and "session" in r:
            self.session_id = r["session"]

        if r['result'] is False:
            raise LoginError(str(r))

    def get_product_def(self):
        method = "magicBox.getProductDefinition"

        params = {
            "name" : "Traffic"
        }
        r = self.request(method=method, params=params)

        if r['result'] is False:
            raise RequestError(str(r))

    def keep_alive(self):
        params = {
            'timeout': 300,
            'active': False
        }

        method = "global.keepAlive"
        r = self.request(method=method, params=params)

        if r['result'] is True:
            return True
        else:
            raise RequestError(str(r))

    def get_traffic_info(self):
        method = "RecordFinder.factory.create"

        params = {
            "name" : "TrafficSnapEventInfo"
        }
        r = self.request(method=method, params=params)
        
        if type(r['result']):
            return r['result']
        else:
            raise RequestError(str(r))

    def start_find(self,object_id,milli_from=1558925818,milli_to=1559012218):
        method = "RecordFinder.startFind"
        object_id = object_id
        params = {
            "condition" : {
                "Time" : ["<>",milli_from,milli_to]
            }
        }
        r = self.request(object_id=object_id,method=method, params=params)

        if r['result'] is False:
            raise RequestError(str(r))

    def do_find(self,object_id):
        method = "RecordFinder.doFind"
        object_id = object_id
        params = {
            "count" : 50000
        }
        r = self.request(object_id=object_id,method=method, params=params)

        if r['result'] is False:
            raise RequestError(str(r))
        else:
            return r
            
    def set_config(self, params):
        """Set configurations."""

        method = "configManager.setConfig"
        r = self.request(method=method, params=params)

        if r['result'] is False:
            raise RequestError(str(r))

    def reboot(self):
        """Reboot the device."""

        # Get object id
        method = "magicBox.factory.instance"
        params = ""
        r = self.request(method=method, params=params)
        object_id = r['result']

        # Reboot
        method = "magicBox.reboot"
        r = self.request(method=method, params=params, object_id=object_id)

        if r['result'] is False:
            raise RequestError(str(r))

    def current_time(self):
        """Get the current time on the device."""

        method = "global.getCurrentTime"
        r = self.request(method=method)
        if r['result'] is False:
            raise RequestError(str(r))

        return r['params']['time']

    def ntp_sync(self, address, port, time_zone):
        """Synchronize time with NTP."""

        # Get object id
        method = "netApp.factory.instance"
        params = ""
        r = self.request(method=method, params=params)
        object_id = r['result']

        # NTP sync
        method = "netApp.adjustTimeWithNTP"
        params = {'Address': address, 'Port': port, 'TimeZone': time_zone}
        r = self.request(method=method, params=params, object_id=object_id)

        if r['result'] is False:
            raise RequestError(str(r))

    def get_split(self):
        """Get display split mode."""

        # Get object id
        method = "split.factory.instance"
        params = {'channel': 0}
        r = self.request(method=method, params=params)
        object_id = r['result']

        # Get split mode
        method = "split.getMode"
        params = ""
        r = self.request(method=method, params=params, object_id=object_id)

        if r['result'] is False:
            raise RequestError(str(r))

        mode = int(r['params']['mode'][5:])
        view = int(r['params']['group']) + 1

        return mode, view

    def attach_event(self, event = []):
        """Attach a event to current session"""
        method = "eventManager.attach"
        if(event is None):
            return
        params = {
            'codes' : [*event]
        }

        r = self.request(method=method, params=params)

        if r['result'] is False:
            raise RequestError(str(r))

        return r['params']

    def listen_events(self, _callback= None):
        """ Listen for envents. Attach an event before using this function """
        url = "http://{host}/SubscribeNotify.cgi?sessionId={session}".format(host=self.host,session=self.session_id)
        response = self.s.get(url, stream= True)

        buffer = ""
        for chunk in response.iter_content(chunk_size=1):
            buffer += chunk.decode("utf-8")
            if (buffer.endswith('</script>') is True):
                if _callback:
                    _callback(buffer)
                buffer = ""

    def set_split(self, mode, view):
        """Set display split mode."""

        if isinstance(mode, int):
            mode = "Split{}".format(mode)
        group = view - 1

        # Get object id
        method = "split.factory.instance"
        params = {'channel': 0}
        r = self.request(method=method, params=params)
        object_id = r['result']

        # Set split mode
        method = "split.setMode"
        params = {'displayType': "General",
                  'workMode': "Local",
                  'mode': mode,
                  'group': group}
        r = self.request(method=method, params=params, object_id=object_id)

        if r['result'] is False:
            raise RequestError(str(r))
        
    """Get last ANPR/LPR available event."""
    def get_last_plate(self):
        # Set and get the factory object_id
        object_id = self.get_traffic_info()

        # Set search interval (00:00:00 a 23:59:59 from Now)
        now = int(time.time())
        start_of_day = now - (now % 86400)  # 00:00:00
        end_of_day = start_of_day + 86400 - 1  # 23:59:59

        # Llamar a start_find con el rango de tiempo
        self.start_find(object_id, milli_from=start_of_day, milli_to=end_of_day)

        # Call to do_find for getting the records
        r = self.do_find(object_id)

        # Check if records are found
        if "params" in r and "records" in r["params"]:
            records = r["params"]["records"]
            if records:
                # Sorts the records by the "Time" field in ascending order
                sorted_records = sorted(records, key=lambda x: x['Time'], reverse=True)
        
                # Returns the first (most recent) record
                return sorted_records[0]
            else:
                raise RequestError("❌ No records found.")
        else:
            raise RequestError("❌ Error obtaining patent records.")
        
    """Open barrier."""
    def open_barrier(self):
        method = "trafficSnap.openStrobe"
        params = {
            "info": {
                "openType": "Test",
                "plateNumber": ""
            }
        }

        r = self.request(method=method, params=params)
        
        if r.get("result") is True:
            print("✅ Barrier successfully opened!")
        else:
            raise RequestError(f"❌ Cannot open barrier: {r}")
        
        
    """Capture snapShot manually."""
    def snap_shot(self):
        method = "trafficSnap.manSnap"

        r = self.request(method=method)
        
        if r.get("result") is True:
            print("✅ Snapshot captured!")
        else:
            raise RequestError(f"❌ The snapshot couldn't be captured: {r}")


class LoginError(Exception):
    pass


class RequestError(Exception):
    pass