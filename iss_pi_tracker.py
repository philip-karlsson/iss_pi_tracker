import time
import json
import urllib.request
import math
from threading import Thread
import RPi.GPIO as GPIO
import datetime

import requests
import json

from socket import timeout

def get_iss_pos_now():
    iss_now_url = 'http://api.open-notify.org/iss-now.json'
    try:
        resp = urllib.request.urlopen(iss_now_url, timeout=10)
    except Exception as e:
        print('Timeout in get pos')
        print('Exception:' + str(e))
        return None
    res = json.loads(resp.read().decode())
    location = res['iss_position']
    lat = float(location['latitude'])
    lon = float(location['longitude'])
    return {'lat' : lat, 'lon' : lon}

def when_is_iss_at(lat, lon):
    url = 'http://api.open-notify.org/iss-pass.json'
    url = url + '?lat=' + str(lat) + '&lon=' + str(lon)
    try:
        resp = urllib.request.urlopen(url, timeout=10)
    except Exception as e:
        print('Timeout in when is iss')
        print('Exception:' + str(e))
        return None
    res = json.loads(resp.read().decode())
    passes = res['response']
    ret = passes[0]
    currentTime = time.time()
    if currentTime > ret['risetime'] + ret['duration']:
        for i in range(0, len(passes)):
            if passes[i]['risetime'] > currentTime:
                ret = passes[i]
                break
    return ret

def get_elev(c1, c2):
    x = c1['x']
    y = c1['y']
    z = c1['z']
    dx = c2['x'] - x
    dy = c2['y'] - y
    dz = c2['z'] - z
    e = (x*dx + y*dy + z*dz) / math.sqrt(((x*x + y*y + z*z) * (dx*dx + dy*dy + dz*dz)))
    elev = 90 - math.degrees(math.acos(e))
    return elev

def get_azimuth(c1, c2):
    phi_1 = math.radians(c1['lat'])
    phi_2 = math.radians(c2['lat'])
    delta_lambda = math.radians(c2['lon'] - c1['lon'])
    y = math.sin(delta_lambda) * math.cos(phi_2)
    x = math.cos(phi_1) * math.sin(phi_2) - math.sin(phi_1) * math.cos(phi_2) * math.cos(delta_lambda)
    theta = math.atan2(y, x)
    return int(math.degrees(theta) + 360) % 360

def get_distance_between(c1, c2):
    return math.sqrt(math.pow((c1['x'] - c2['x']), 2) + math.pow((c1['y'] - c2['y']), 2) + math.pow((c1['z'] - c2['z']), 2))

def get_3d_coord(lat, lon, r):
    theta = math.radians(lat)
    phi = math.radians(lon)
    x = r * (math.cos(theta) * math.cos(phi))
    y = r * (math.cos(theta) * math.sin(phi))
    z = r * (math.sin(theta))
    return {'x': x, 'y': y, 'z': z}

def calculate_eucladian_distance_to_iss(iss_lat, iss_lon, src_lat, src_lon):
    """ Returns the distance in km """
    # We are approx. 6400km from the centero of the earth
    local_coord = get_3d_coord(src_lat, src_lon, 6400)
    # Iss is approx. 400km above the earth
    iss_coord = get_3d_coord(iss_lat, iss_lon, 6808)
    return get_distance_between(iss_coord, local_coord)

def get_hdg_letter(az):
    hdgLetter = ''
    if az == 0:
        hdgLetter = 'N'
    elif az > 0 and az < 90:
        hdgLetter = 'NE'
    elif az == 90:
        hdgLetter = 'E'
    elif az > 90 and az < 180:
        hdgLetter = 'SE'
    elif az == 180:
        hdgLetter = 'S'
    elif az > 180 and az < 270:
        hdgLetter = 'SW'
    elif az == 270:
        hdgLetter = 'W'
    elif az > 270 and az < 360:
        hdgLetter = 'NW'
    return hdgLetter

# Global variables
# Use led 36 to indicate passage
class Iss_Tracker:
    def __init__(self):
        # Setup display
        #serial = i2c(port=1, address=0x3C)
        #self.display = sh1106(serial)
        self.LED = 36
        # The local coordinates
        self.local_lat = 56.108715
        self.local_lon = 15.661008
        self.dc_period = 1 # seconds
        self.dc = 0
        self.iss_poll_rate = 5.00 # as suggested by open-notify.org
        self.far_dc_dist = 4000.00 #km 
        self.close_dc_dist = 500.00 #km
        self.dc_range = self.far_dc_dist - self.close_dc_dist
        # We are approx. 6400km from the centero of the earth
        self.local_coord = get_3d_coord(self.local_lat, self.local_lon, 6400)

    def setup_pwm_thread(self):
        self.t = Thread(target=self.gpio_pwm_thread)
        self.t.start()

    def gpio_setup(self):
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.LED, GPIO.OUT)
        GPIO.output(self.LED, GPIO.LOW)

    def gpio_pwm_thread(self):
        """ Responsible for creating DC """
        while True:
            if self.dc == 0:
                GPIO.output(self.LED, 0)
                time.sleep(self.dc_period)
            elif self.dc == 100:
                GPIO.output(self.LED, 1)
                time.sleep(self.dc_period)
            else:
                act_time = self.dc * 0.01 * self.dc_period
                off_time = self.dc_period - act_time
                # Hack to modulate period instead of DC
                # This way, we change period instead of DC for indication
                act_time = off_time
                # Set gpio on
                GPIO.output(self.LED, 1)
                time.sleep(act_time)
                # Set gpio off
                GPIO.output(self.LED, 0)
                time.sleep(off_time)


    def calc_dc_from_distance(self, distance):
        fault = distance - self.close_dc_dist
        if fault <= 0:
            dc = 100
        else:
            dc = 100 - (100 * (fault / self.dc_range))
        if dc < 1:
            dc = 1
        return dc

    def update_display(self, distance, iss_lat, iss_lon, time_of_next_rise, time_to, elev, az):
        nex = time.ctime(time_of_next_rise)
        nex = ' '.join(nex.split(' ')[:-1])
        nex = ' '.join(nex.split(' ')[1:])

        distStr = 'ISS Dist:%.2fkm' % distance
        issLatStr = 'ISS Lat:%.2fdeg.' % iss_lat
        issLonStr = 'ISS Lon:%.2fdeg.' % iss_lon
        nextStr = 'Next:' + nex
        hdgLetter = get_hdg_letter(az)
        altHdgStr = 'Hdg:%d%s Alt:%d' % (int(az), hdgLetter, int(elev))

        report = {
                "distStr": distStr,
                "issLatStr": issLatStr,
                "issLonStr": issLonStr,
                "nextStr": nextStr,
                "hdgLetter": hdgLetter,
                "altHdgStr": altHdgStr,
                "time_to": time_to
        }

        try:
            r = requests.post('http://localhost:6666/handle', json=report, timeout=1.5)
        except:
            pass

    def main_thread(self):
        """ Responsible for polling the iss position and writing DC """
        while True:
            # Get the current ISS pos
            iss_pos = get_iss_pos_now()
            if iss_pos == None:
                time.sleep(5)
                continue
            iss_coord = get_3d_coord(iss_pos['lat'], iss_pos['lon'], 6808)
            dist = get_distance_between(iss_coord, self.local_coord)
            elev = get_elev(self.local_coord, iss_coord)
            az = get_azimuth({'lat': self.local_lat, 'lon': self.local_lon}, iss_pos)
            # Get next local sight
            time.sleep(1.00) #Wait one second before the next req
            res = when_is_iss_at(self.local_lat, self.local_lon)
            if res == None:
                time.sleep(5)
                continue
            rt = res['risetime']
            dur = res['duration']
            ft = rt + dur
            currentTime = time.time()
            if currentTime > rt and currentTime < ft:
                self.dc = self.calc_dc_from_distance(dist)
                timediff = str(datetime.timedelta(seconds=ft-currentTime))
                timediff = ''.join(timediff.split('.')[:-1])
                time_to = 'Set in:' + timediff
            else:
                timediff = str(datetime.timedelta(seconds=rt-currentTime))
                timediff = ''.join(timediff.split('.')[:-1])
                time_to = 'Rise in:' + timediff
                self.dc = 0
            self.update_display(dist, iss_pos['lat'], iss_pos['lon'], rt, time_to, elev, az)
            time.sleep(4.00)

def main():
    tracker = Iss_Tracker()
    tracker.gpio_setup()
    tracker.setup_pwm_thread()
    tracker.main_thread()

if __name__ == "__main__":
    main()
