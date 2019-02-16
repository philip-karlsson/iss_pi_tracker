import time
import RPi.GPIO as GPIO
import json
import urllib.request

# Use led 36 to indicate passage
LED = 36

sturkoe_lat = 56.108715
sturkoe_long = 15.661008

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
    print(passes[0])
    for pa in passes:
        print(time.ctime(pa['risetime']))

def setup():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(LED, GPIO.OUT)
    GPIO.output(LED, GPIO.LOW)

def process():
    resp = when_is_iss_at(sturkoe_lat, sturkoe_long)
    GPIO.output(LED, 1)
    time.sleep(0.5)
    GPIO.output(LED, 0)
    time.sleep(0.5)
    # resp = get_iss_pos_now()
    # print(resp['lat'])
    # print(resp['lon'])
    # print(time.ctime(resp['response'][0]['risetime']))

def main():
    setup()
    while True:
        process()

if __name__ == "__main__":
    main()
