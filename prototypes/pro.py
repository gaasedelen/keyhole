from Tkinter import Tk, PhotoImage
import tobii_research as tr
import time

t = tr.find_all_eyetrackers()[0]

def stream_error_callback(stream_error_data):
    print(stream_error_data)

def eye_image_callback(eye_image_data):
    print("System time: {0}, Device time {1}, Camera id {2}".format(eye_image_data['system_time_stamp'],
                                                                     eye_image_data['device_time_stamp'],
                                                                     eye_image_data['camera_id']))
 
    image = PhotoImage(data=base64.standard_b64encode(eye_image_data['image_data']))
    print("{0} width {1}, height {2}".format(image, image.width(), image.height()))

print("Subscribing to stream errors for eye tracker with serial number {0}.".format(t.serial_number))
t.subscribe_to(tr.EYETRACKER_STREAM_ERRORS, stream_error_callback, as_dictionary=True)

def gaze_data_callback(gaze_data):
    # Print gaze points of left and right eye
    #print("Left eye: ({gaze_left_eye}) \t Right eye: ({gaze_right_eye})".format(
    #    gaze_left_eye=gaze_data['left_gaze_point_on_display_area'],
    #    gaze_right_eye=gaze_data['right_gaze_point_on_display_area']))
    #print gaze_data.left_eye.gaze_point.position_on_display_area
    pass

t.subscribe_to(tr.EYETRACKER_GAZE_DATA, gaze_data_callback)

raw_input()
# Trigger an error by subscribing to something not supported.
t.subscribe_to(tr.EYETRACKER_EYE_IMAGES, eye_image_callback)
time.sleep(1)
#t.unsubscribe_from(tr.EYETRACKER_EYE_IMAGES, eye_image_callback)

#t.unsubscribe_from(tr.EYETRACKER_STREAM_ERRORS, stream_error_callback)
print("Unsubscribed from stream errors.")

#root = Tk()
#print("Subscribing to eye images for eye tracker with serial number {0}.".format(t.serial_number))
#t.subscribe_to(tr.EYETRACKER_EYE_IMAGES, eye_image_callback, as_dictionary=True)

# Wait for eye images.
#time.sleep(20)

#t.unsubscribe_from(tr.EYETRACKER_EYE_IMAGES, eye_image_callback)
#print("Unsubscribed from eye images.")
#root.destroy()