import time
import json
import urllib.request
import math

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

def setup():
    pass

def process():
    # resp = when_is_iss_at(sturkoe_lat, sturkoe_long)
    resp = get_iss_pos_now()
    iss_lat = resp['lat']
    iss_lon = resp['lon']
    dist = calculate_eucladian_distance_to_iss(iss_lat, iss_lon, sturkoe_lat, sturkoe_long)
    print('ISS distance form sturkoe:' + str(dist) + 'km')
    time.sleep(5.0)
    # print(time.ctime(resp['response'][0]['risetime']))

def main():
    setup()
    while True:
        process()

if __name__ == "__main__":
    main()
