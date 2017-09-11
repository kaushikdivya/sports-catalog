# -*- coding: utf-8 -*-

import psycopg2
import sys


con = None

try:
    con = psycopg2.connect(
        "host='localhost' dbname='Catalog' user='vagrant' password='vagrant'"
    )
    cur = con.cursor()
    cur.execute(
        """CREATE TABLE category ("""
            """id SERIAL PRIMARY KEY, """
            """name VARCHAR(25) NOT NULL, """
            """created_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp(), """
            """modified_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp(), """
            """expiry_date TIMESTAMP WITH TIME ZONE"""
        """)"""
    )
    cur.execute("CREATE TABLE category_items (id SERIAL PRIMARY KEY, category_id INTEGER REFERENCES category(id), name VARCHAR(25) NOT NULL, description text NOT NULL, created_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp(), modified_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp(), expiry_date TIMESTAMP WITH TIME ZONE)")
    cur.execute("CREATE TABLE user_info (id SERIAL PRIMARY KEY, email VARCHAR(250) NOT NULL, name VARCHAR(250) NOT NULL, picture VARCHAR(250), created_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp(), modified_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp(), expiry_date TIMESTAMP WITH TIME ZONE)")
    cur.execute("INSERT INTO category (name) VALUES ('Soccer'),('Basketball'),('Baseball'),('Frisbee'),('Snowboarding'),('Rock Climbing'),('Foosball'),('Skating'),('Hockey')")
    cur.execute("INSERT INTO category_items (category_id, name, description) VALUES (9, 'Stick', 'A hockey stick is a piece of equipment used in field hockey, ice hockey, roller hockey or underwater hockey to move the ball or puck.'),(5, 'Snowboard', 'Snowboards are boards that are usually the width of ones foot longways, with the ability to glide on snow. Snowboards are differentiated from monoskis by the stance of the user. In monoskiing, the user stands with feet inline with direction of travel (facing tip of monoski/downhill) (parallel to long axis of board), whereas in snowboarding, users stand with feet transverse (more or less) to the longitude of the board. Users of such equipment may be referred to as snowboarders.'),(5, 'Snowboard', 'Snowboards are boards that are usually the width of ones foot longways, with the ability to glide on snow. Snowboards are differentiated from monoskis by the stance of the user. In monoskiing, the user stands with feet inline with direction of travel (facing tip of monoski/downhill) (parallel to long axis of board), whereas in snowboarding, users stand with feet transverse (more or less) to the longitude of the board. Users of such equipment may be referred to as snowboarders.'), (1, 'Jersey', 'The Laws of the Game set out the basic equipment which must be worn by all players in Law 4: The Players Equipment. Five separate items are specified: shirt (also known as a jersey), shorts, socks (also known as stockings), footwear and shin pads. Goalkeepers are allowed to wear tracksuit bottoms instead of shorts.'),(1, 'Shin Guards', 'A shin guard or shin pad is a piece of equipment worn on the front of a player’s shin to protect them from injury. These are commonly used in sports including association football (soccer), baseball, ice hockey, field hockey, lacrosse, rugby, cricket, and other sports. This is due to either being required by the rules/laws of the sport or worn voluntarily by the participants for protective measures.')")
    con.commit()
except psycopg2.DatabaseError, e:
    if con:
        con.rollback()

    print 'Error %s' % e
    sys.exit(1)

finally:
    if con:
        con.close()
