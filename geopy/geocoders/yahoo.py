import json
import logging
from urllib import urlencode
from urllib2 import urlopen, HTTPError
import xml.dom.minidom

from geopy import util
from geopy import Point, Location
from geopy.geocoders.base import Geocoder

log = logging.getLogger(__name__)


class Yahoo(Geocoder):

    BASE_URL = "http://api.local.yahoo.com/MapsService/V1/geocode?%s"

    def __init__(self, app_id, format_string='%s', output_format='xml'):
        self.app_id = app_id
        self.format_string = format_string
        self.output_format = output_format.lower()

    def geocode(self, string):
        params = {'location': self.format_string % string,
                  'output': self.output_format,
                  'appid': self.app_id
                 }
        url = self.BASE_URL % urlencode(params)
        return self.geocode_url(url)

    def geocode_url(self, url):
        log.debug("Fetching %s..." % url)
        page = urlopen(url)

        parse = getattr(self, 'parse_' + self.output_format)
        return parse(page)

    def parse_xml(self, page):
        if not isinstance(page, basestring):
            page = util.decode_page(page)
        
        doc = xml.dom.minidom.parseString(page)
        results = doc.getElementsByTagName('Result')
        precision = results[0].getAttribute('precision')
        
        def parse_result(result):
            strip = ", \n"
            address = util.get_first_text(result, 'Address', strip)
            city = util.get_first_text(result, 'City', strip)
            state = util.get_first_text(result, 'State', strip)
            zip = util.get_first_text(result, 'Zip', strip)
            country = util.get_first_text(result, 'Country', strip)
            city_state = util.join_filter(", ", [city, state])
            place = util.join_filter(" ", [city_state, zip])
            location = util.join_filter(", ", [address, place, country])
            latitude = util.get_first_text(result, 'Latitude') or None
            longitude = util.get_first_text(result, 'Longitude') or None
            if latitude and longitude:
                point = Point(latitude, longitude)
            else:
                point = None
            return Location(location, point, {
                'Address': address,
                'City': city,
                'State': state,
                'Zip': zip,
                'Country': country,
                'precision': precision
            })
        
        # Todo: exactly_one needs to be here?
        return [parse_result(result) for result in results]


class YahooPlaceFinder(Geocoder):

    BASE_URL = "http://where.yahooapis.com/geocode?%s"

    def __init__(self, app_id):
        self.app_id = app_id
        
    def geocode(self, string, exactly_one=True):
        params = {  'flags': 'j',  #json
                    'q': string 
                 }
        url = self.BASE_URL % urlencode(params)
        return self.geocode_url(url, exactly_one)

    def geocode_url(self, url, exactly_one=True):
        log.debug("Fetching %s..." % url)
        page = urlopen(url)
        
        parse = getattr(self, 'parse_json')
        return parse(page, exactly_one)

    def parse_json(self, page, exactly_one=True):
        json_str = page.read()
        parsed = json.loads(json_str)
        results = parsed['ResultSet']['Results']
        
        if (exactly_one and len(results) != 1):
            raise ValueError("Didn't find exactly one placemark! " \
                "(Found %d.)" % len(results))
                
        def parse_result(result):
            location = "%(house)s %(street)s %(city)s %(state)s (%(statecode)s) %(country)s (%(countrycode)s) %(uzip)s" % result 
            location = location.strip().replace('  ','')
            
            latitude = result.get('latitude')
            longitude = result.get('longitude')
            if latitude and longitude:
                point = Point(float(latitude), float(longitude))
            else:
                point = None
            
            return Location(location, point, result)
        
        # Todo: Fix: Not sure how to return results here
        # The geocoders_old seem to be returning a different format.
        # need to make these as consistent.
        if exactly_one:
            return parse_result(results[0])
        else:
            return (parse_result(result) for result in results)
        
