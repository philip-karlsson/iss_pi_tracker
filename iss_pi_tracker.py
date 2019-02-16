import time
import json
import urllib.request
import math
from threading import Thread
import RPi.GPIO as GPIO
import datetime

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import sh1106


def get_iss_pos_now():
    iss_now_url = 'http://api.open-notify.org/iss-now.json'
    resp = urllib.request.urlopen(iss_now_url)
    res = json.loads(resp.read().decode())
    location = res['iss_position']
    lat = float(location['latitude'])
    lon = float(location['longitude'])
    return {'lat' : lat, 'lon' : lon}

def when_is_iss_at(lat, lon):
    url = 'http://api.open-notify.org/iss-pass.json'
    url = url + '?lat=' + str(lat) + '&lon=' + str(lon)
    resp = urllib.request.urlopen(url)
    res = json.loads(resp.read().decode())
    passes = res['response']
    ret = passes[0]
    currentTime = time.time()
    if currentTime > ret['risetime']:
        for i in range(0, len(passes)):
            if passes[i]['risetime'] > currentTime:
                ret = passes[i]
                break
    return ret

def get_distance_between(c1, c2):
    return math.sqrt(math.pow((c1['x'] - c2['x']), 2) + math.pow((c1['y'] - c2['y']), 2) + math.pow((c1['z'] - c2['z']), 2))

def get_3d_coord(lat, lon, r):
    theta = lat * (math.pi / 180.00)
    phi = lon * (math.pi / 180.00)
    x = r * (math.cos(phi) * math.cos(theta))
    y = r * (math.cos(phi) * math.sin(theta))
    z = r * (math.sin(theta))
    return {'x': x, 'y': y, 'z': z}

def calculate_eucladian_distance_to_iss(iss_lat, iss_lon, src_lat, src_lon):
    """ Returns the distance in km """
    # We are approx. 6400km from the centero of the earth
    local_coord = get_3d_coord(src_lat, src_lon, 6400)
    # Iss is approx. 400km above the earth
    iss_coord = get_3d_coord(iss_lat, iss_lon, 6808)
    return get_distance_between(iss_coord, local_coord)

# Global variables
# Use led 36 to indicate passage
class Iss_Tracker:
    def __init__(self):
        # Setup display
        serial = i2c(port=1, address=0x3C)
        self.display = sh1106(serial)
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

    def update_display(self, distance, iss_lat, iss_lon, time_of_next_rise, duration):
        dur = str(datetime.timedelta(seconds=duration))
        nex = time.ctime(time_of_next_rise)
        nex = ' '.join(nex.split(' ')[:-1])
        nex = ' '.join(nex.split(' ')[1:])

        distStr = 'ISS Dist:%.2fkm' % distance
        issLatStr = 'ISS Lat:%.2fdeg.' % iss_lat
        issLonStr = 'ISS Lon:%.2fdeg.' % iss_lon
        nextStr = 'Next:' + nex
        durStr = 'Length:' + dur
        with canvas(self.display) as draw:
            draw.text((0, 0), distStr, fill='white')
            draw.text((0, 12), issLatStr, fill='white')
            draw.text((0, 24), issLonStr, fill='white')
            draw.text((0, 36), nextStr, fill='white')
            draw.text((0, 48), durStr, fill='white')

    def main_thread(self):
        """ Responsible for polling the iss position and writing DC """
        while True:
            # Get the current ISS pos
            iss_pos = get_iss_pos_now()
            dist = calculate_eucladian_distance_to_iss(iss_pos['lat'], iss_pos['lon'], self.local_lat, self.local_lon)
            # Get next local sight
            res = when_is_iss_at(self.local_lat, self.local_lon)
            rt = res['risetime']
            dur = res['duration']
            ft = rt + dur
            currentTime = time.time()
            if currentTime > rt and currentTime < ft:
                self.dc = self.calc_dc_from_distance(dist)
            else:
                self.dc = 0
            self.update_display(dist, iss_pos['lat'], iss_pos['lon'], rt, dur)
            time.sleep(5.00)

def main():
    tracker = Iss_Tracker()
    tracker.gpio_setup()
    tracker.setup_pwm_thread()
    tracker.main_thread()

if __name__ == "__main__":
    main()
