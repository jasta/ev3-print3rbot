#!/usr/bin/env python
# coding: utf-8

import math, os, time
from ev3dev import *

from svg.parser import parse_path
from svg.path import Path, Line, Arc, CubicBezier, QuadraticBezier

class simple_touch:
	def __init__(self, sensor):
		self.sensor = sensor

class simple_touch_color(simple_touch):
    def value(self):
		if self.sensor.value() > 25:
			return 1
		else:
			return 0

class simple_touch_actual(simple_touch):
	def value(self):
		return self.sensor.value()
        
class mymotor(motor):
    def stop(self, stop_command='coast'):
        self.stop_command = stop_command
        self.command = "stop"
    
    def reset_position(self, value = 0):
        self.stop()
        iter = 1
        while (self.position != 0 and iter < 10):
            iter += 1
            try:
                self.position = value
            except:
                print "impossible to fix position, attempt",iter-1,"on 10."
            time.sleep(0.05)
            
    def rotate_forever(self, speed=480, regulate='on', stop_command='brake'):
        self.stop_command = stop_command
        if regulate=='on':
            self.speed_sp = int(speed)
        else:
            self.duty_cycle_sp = int(speed)
        self.speed_regulation_enabled = regulate
        self.command = 'run-forever'

    def goto_position(self, position, speed=480, up=0, down=0, regulate='on', stop_command='brake', wait=0):
        self.stop_command = stop_command
        self.speed_regulation_enabled = regulate
        self.ramp_up_sp,self.ramp_down_sp = up,down
        if regulate=='on':
            self.speed_sp = speed
        else:
            self.duty_cycle_sp = speed
        self.position_sp = position
        sign = math.copysign(1, self.position - position)
        self.command = 'run-to-abs-pos'
        
        if (wait):
            new_pos = self.position
            nb_same = 0
            while (sign * (new_pos - position) > 5):
                time.sleep(0.05)
                old_pos = new_pos
                new_pos = self.position
                if old_pos == new_pos:
                    nb_same += 1
                else:
                    nb_same = 0
                if nb_same > 10:
                    break
            time.sleep(0.05)
            if (not stop_command == "hold"):
                self.stop()


class Writer():
    
    def __init__(self, calibrate=True):
        self.mot_A    = mymotor(OUTPUT_A)

        self.mot_B    = mymotor(OUTPUT_C)
        self.mot_lift = mymotor(OUTPUT_B)

        self.touch_A  = simple_touch_color(color_sensor(INPUT_1))
        self.touch_B  = simple_touch_actual(touch_sensor(INPUT_2))
        
        if (calibrate):
            self.calibrate()
        self.pen_up()

    def pen_up (self):
        self.mot_lift.goto_position(40, 200, regulate = 'on', stop_command='brake', wait = 0)
        time.sleep(0.1)
        
    def pen_down(self):
        self.mot_lift.goto_position(10, 200, regulate = 'on', stop_command='brake', wait = 1)
        time.sleep(0.1)

    def calibrate (self):
        self.calibrate_lift()
        self.calibrate_arms()
        
    def calibrate_lift(self):
        self.mot_lift.rotate_forever(speed=-50, regulate='off')
        time.sleep(0.5)
        while(abs(self.mot_lift.speed) > 5):
            time.sleep(0.001)
        self.mot_lift.stop()
        time.sleep(0.1)
        self.mot_lift.reset_position()
        time.sleep(0.1)
        self.mot_lift.goto_position(40, speed=400, regulate='on', stop_command='brake', wait=1)
        time.sleep(0.1)
        self.mot_lift.reset_position()
        time.sleep(1)

        self.pen_up()

    def calibrate_arms(self):
        self.mot_A.reset_position()
        self.mot_B.reset_position()

        if (self.touch_A.value()):
            self.mot_A.goto_position(-200, speed=400, regulate='on', stop_command='coast', wait=1)
        if (self.touch_B.value()):
            self.mot_B.goto_position(200, speed=400, regulate='on', stop_command='coast', wait=1)
        self.mot_B.rotate_forever(speed=-50, regulate='off')   
        self.mot_A.rotate_forever(speed=50, regulate='off')   
        stop_A = stop_B = False
        start = time.time()
        while True:
            touch_A, touch_B = self.touch_A.value(), self.touch_B.value()
            if (not stop_A and touch_A):
                pos = self.mot_A.position
                self.mot_A.stop()
                self.mot_A.goto_position(pos, speed=-400, regulate='on', stop_command='hold')
                stop_A = True
            if (not stop_B and touch_B):
                pos = self.mot_B.position
                self.mot_B.goto_position(pos, speed=400, regulate='on', stop_command='hold')
                stop_B = True
            if (stop_B and stop_A):
                break
            if (time.time() - start > 10):
                self.mot_A.stop()
                self.mot_B.stop()
                break
            time.sleep(0.05)
        time.sleep(1)
        self.mot_A.reset_position()
        self.mot_B.reset_position()
		# Mechanical TODO: color sensor arm pushes back too far...
        #self.mot_A.goto_position(-200, speed=400, regulate='on', stop_command='hold', wait=0)
        self.mot_B.goto_position(200, speed=400, regulate='on', stop_command='hold', wait=1)
        time.sleep(1)
        self.mot_A.stop()
        self.mot_B.stop()
        self.mot_A.reset_position()
        self.mot_B.reset_position()

    # All coordinates are in Lego distance (1 = distance between two holes center)
    # Coordinates of gear centre A
    xA, yA = 0.,0.
    # Coordinates of gear centre B
    xB, yB = 6.,0.
    # Length between articulation and pen
    r1 = 14.
    # Length between gear centre and articulation
    r2 = 11.

    #      .E   (pen is in coordinates E = (xE,yE))
    #     / \
    #    /   \
    #   /     \
    # C.       .D
    #   \     /
    #    \   /
    #    A. .B
    #   -------
    #   [robot]
    #   -------

    ## Computes the intersection of 2 circles of centres x0,y0 and x1,y1 and radius resp. R0 and R1.
    @staticmethod
    def get_coord_intersec (x0, y0, x1, y1, R0, R1):
        if y0 == y1:
            y0+=0.1
        N = R1*R1 - R0*R0 - x1*x1 + x0*x0 - y1*y1 + y0*y0
        N /= 2.*(y0-y1)
        A = ((x0-x1)/(y0-y1))*((x0-x1)/(y0-y1)) + 1.
        B = 2.*y0 * (x0-x1)/(y0-y1) - 2.*N*(x0-x1)/(y0-y1) - 2.*x0
        C = x0*x0 + y0*y0 + N*N -  R0*R0 - 2.*y0*N
        delta = math.sqrt(B*B - 4.*A*C)
        xA_ = (-B + delta) / (2.*A)
        xB_ = (-B - delta) / (2.*A)
        yA_ = N - xA_ * (x0-x1)/(y0-y1)
        yB_ = N - xB_ * (x0-x1)/(y0-y1)
        return (xA_,yA_),(xB_,yB_)

    ## Converts coordinates xE, yE to angles of robot arms.
    @staticmethod
    def coordinates_to_angles (xE, yE):
        try:
            ((xIA, yIA), (xIA2, yIA2)) = Writer.get_coord_intersec (xE, yE, Writer.xA, Writer.yA, Writer.r1, Writer.r2)
            if xIA > xIA2:
                xIA = xIA2
                yIA = yIA2
            ((xIB, yIB), (xIB2, yIA2)) = Writer.get_coord_intersec (xE, yE, Writer.xB, Writer.yB, Writer.r1, Writer.r2)
            if xIB < xIB2:
                xIB = xIB2
                yIB = yIB2
        except:
            return None  
        alpha = 180. - 360 * math.acos((xIA-Writer.xA)/Writer.r2) / (2.*math.pi)
        beta =  360. * math.acos((xIB-Writer.xB)/Writer.r2) / (2.*math.pi) 
        return (alpha, beta)

    ## converts coordinates x,y into motor position
    @staticmethod
    def coordinates_to_motorpos (x, y):
        def angle_to_pos (angle):
            #0     = 14
            #-2970 = 90
            return ((angle-14.) * 2970. / (90.-14.))
        (alpha, beta) = Writer.coordinates_to_angles (x, y)
        print('coordinates_to_angles(%f,%f)=(%f,%f)' % (x, y, alpha, beta))
        return angle_to_pos (alpha), -angle_to_pos (beta)

    ## Converts angles of arms to coordinates.
    @staticmethod
    def angles_to_coordinates (alpha, beta):
        xC = Writer.xA - Writer.r2 * math.cos((2.*math.pi) * alpha/360.)
        yC = Writer.yA + Writer.r2 * math.sin((2.*math.pi) * alpha/360.)
        xD = Writer.xB + Writer.r2 * math.cos((2.*math.pi) * beta/360.)
        yD = Writer.yB + Writer.r2 * math.sin((2.*math.pi) * beta/360.)
        ((xE, yE), (xE2, yE2)) = Writer.get_coord_intersec (xC, yC, xD, yD, Writer.r1, Writer.r1)
        if yE2 > yE:
            xE = xE2
            yE = yE2
        return xE, yE

    def get_coords(self):
        return Writer.motorpos_to_coordinates(self.mot_B.position, self.mot_A.position)

    ## Converts motor position to coordinates
    @staticmethod
    def motorpos_to_coordinates (pos1, pos2):
        def pos_to_angle (pos):
            #0     = 14
            #-2970 = 90
            return 14. + pos * (90.-14) / 2970.
        
        (alpha, beta) = (pos_to_angle(pos1), pos_to_angle(-pos2))
        return Writer.angles_to_coordinates (alpha, beta)
    
    @staticmethod
    def get_angle (xA, yA, xB, yB, xC, yC):
        ab2 = (xB-xA)*(xB-xA) + (yB-yA)*(yB-yA)
        bc2 = (xC-xB)*(xC-xB) + (yC-yB)*(yC-yB)
        ac2 = (xC-xA)*(xC-xA) + (yC-yA)*(yC-yA)
        try:
            cos_abc = (ab2 + bc2 - ac2) / (2*math.sqrt(ab2) * math.sqrt(bc2))
            return 180 - (360. * math.acos(cos_abc) / (2 * math.pi))
        except:
            return 180

    def set_speed_to_coordinates (self,x,y,max_speed,initx=None,inity=None,brake=0.):
        posB, posA = self.mot_B.position, self.mot_A.position
        myx, myy = Writer.motorpos_to_coordinates (posB, posA)
        dist = math.sqrt((myx-x)*(myx-x) + (myy-y)*(myy-y))
        if (initx or inity):
            too_far = (180-Writer.get_angle(initx, inity, x, y, myx, myy) >= 90)
        else:
            too_far = False
        if too_far or (dist < 0.1 and brake < 1.) or dist < 0.05:
            return 0

        nextx = myx + (x - myx) / (dist * 100.)
        nexty = myy + (y - myy) / (dist * 100.)

        print('given=(%f,%f); next=(%f,%f)' % (x, y, nextx, nexty))
        
        next_posB, next_posA = Writer.coordinates_to_motorpos (nextx, nexty)
        print('next_pos=(%f,%f)' % (next_posB, next_posA))
        
        speed = max_speed
        slow_down_dist = (max_speed / 50.)
        if (dist < slow_down_dist):
            speed -= (slow_down_dist-dist)/slow_down_dist * (brake * (max_speed-20))/1.

        distB = (next_posB - posB)
        distA = (next_posA - posA)
        if abs(distB) > abs(distA):
            speedB = speed
            speedA = abs(speedB / distB * distA)
        else:
            speedA = speed
            speedB = abs(speedA / distA * distB)
        
        self.mot_B.rotate_forever((math.copysign(speedB, distB)), regulate='off')
        self.mot_A.rotate_forever((math.copysign(speedA, distA)), regulate='off')
        return 1
        
    def goto_point (self, x,y, brake=1., last_x=None, last_y=None, max_speed=70.):
        if (last_x == None or last_y == None):
            initposB, initposA = self.mot_B.position, self.mot_A.position
            initx, inity = Writer.motorpos_to_coordinates (initposB, initposA)
        else:
            initx, inity = last_x, last_y
        max_speed_ = 20
        while (self.set_speed_to_coordinates (x,y,max_speed_,initx,inity,brake)):
            max_speed_ += 5
            if max_speed_>max_speed:max_speed_=max_speed
            time.sleep(0.0001)
        if brake == 1:
            self.mot_B.stop(stop_command='brake')
            self.mot_A.stop(stop_command='brake')
            
    def follow_path (self, list_points, max_speed=70):
        pen_change = False
        lastx = lasty = None
        while (len(list_points)>0):
            if type(list_points[0]) is int:
                pen_change = True
                pen = int(list_points.pop(0))
                time.sleep(0.1)
                if pen:
                    self.pen_down()
                else:
                    self.pen_up()
                return self.follow_path (list_points, max_speed)
            (x,y) = list_points.pop(0)
            posB, posA = self.mot_B.position, self.mot_A.position
            myx, myy = Writer.motorpos_to_coordinates (posB, posA)
            try:
                (x2,y2) = list_points[0]
                angle = Writer.get_angle (myx, myy, x, y, x2, y2)
                brake = 1.
                if angle < 45:
                    brake -= (45-angle)/45.
            except:
                brake = 1.
            if pen_change:
                pen_change = False
                brake = 1.
            self.goto_point (x,y,brake,lastx, lasty, max_speed=max_speed)
            lastx, lasty = x, y
        self.mot_A.stop()
        self.mot_B.stop()
        
    def read_svg (self, image_file):
        # Open simple svg created from template.svg with only paths and no transform.
        from xml.dom import minidom
        
        def svg_point_to_coord (svg_point):
            scale = 10.
            ciblex = svg_point.real/scale
            cibley = (272.74-svg_point.imag)/scale
            return (ciblex, cibley)
        def feq(a,b):
            if abs(a-b)<0.0001:
                return 1
            else:
                return 0    
        
        xmldoc = minidom.parse(image_file)

        itemlist = xmldoc.getElementsByTagName('path') 
        itemlist = filter(lambda x: x.attributes['id'].value != "borders", itemlist)
        
        path = [s.attributes['d'].value for s in itemlist]
        
        list_points = []
        actual = (0+0j)
        for p_ in path:
            p__ = parse_path(p_)
            for p in p__:
                start = p.point(0.)
                if not feq(actual,start):
                    list_points.append(0)
                    list_points.append(svg_point_to_coord(start))
                    list_points.append(1)
                if (not isinstance(p, Line)):
                    length = p.length(error=1e-2)
                    for i in range(3,int(math.floor(length)),3):
                        list_points.append(svg_point_to_coord(p.point(i/length)))
                end = p.point(1.)
                list_points.append(svg_point_to_coord(end))
                actual = end
        list_points.append(0)
        return list_points
        

        
    def draw_image (self, image_file = 'images/drawing.svg', max_speed=70.):
        list_points = self.read_svg (image_file)
        
        self.follow_path(list_points, max_speed=max_speed)
    
    def follow_mouse (self, path="/dev/input/by-id/usb-0461_USB_Optical_Mouse-event-mouse"):
        if not os.path.exists(path):
            return
        posB, posA = self.mot_B.position, self.mot_A.position
        startx, starty = Writer.motorpos_to_coordinates (posB, posA)
        self.pen_up()
        pen_up = True
        import evdev
        dev = evdev.Device(path)
        while 1:
            dev.poll()
            time.sleep(0.005)
            if ("BTN_RIGHT" in dev.buttons.keys()):
                #self.pen_up()
                if (dev.buttons["BTN_RIGHT"]):
                    x,y = dev.axes["REL_X"]/100., dev.axes["REL_Y"]/100.
                    ciblex = startx-x
                    cibley = starty+y
                    print ciblex, cibley
                
            if ("BTN_LEFT" in dev.buttons.keys()):
                if (pen_up and dev.buttons["BTN_LEFT"]):
                    pen_up = False
                    self.pen_down()
                elif (not pen_up and not dev.buttons["BTN_LEFT"]):
                    pen_up = True
                    self.pen_up()
            if ("REL_X" in dev.axes.keys()) and ("REL_Y" in dev.axes.keys()):
                x,y = dev.axes["REL_X"]/100., dev.axes["REL_Y"]/100.
                ciblex = startx-x
                cibley = starty+y
                if (not self.set_speed_to_coordinates (ciblex,cibley,brake=1.,max_speed = 100)):
                    self.mot_A.stop()
                    self.mot_B.stop()
    
if __name__ == "__main__":
    wri = Writer(calibrate = False)
    
    wri.pen_up()
    time.sleep(2)
    wri.pen_down()
    time.sleep(2)
    
    #wri.pen_up()
    #wri.draw_image(image_file = 'images/test.svg',max_speed=50)
    #wri.follow_mouse()
    #wri.pen_up()
    
