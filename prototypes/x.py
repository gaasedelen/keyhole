import tobii_research as tr
import time

t = tr.find_all_eyetrackers()[0]

#---------------------------------------------------------------------------

def stream_error_callback(stream_error_data):
    print(stream_error_data)

print("Subscribing to stream errors for eye tracker with serial number {0}.".format(t.serial_number))
t.subscribe_to(tr.EYETRACKER_STREAM_ERRORS, stream_error_callback, as_dictionary=True)

#---------------------------------------------------------------------------

def gaze_data_callback(gaze_data):
    # Print gaze points of left and right eye
    #print("Left eye: ({gaze_left_eye}) \t Right eye: ({gaze_right_eye})".format(
    #    gaze_left_eye=gaze_data['left_gaze_point_on_display_area'],
    #    gaze_right_eye=gaze_data['right_gaze_point_on_display_area']))
    print gaze_data

t.subscribe_to(tr.EYETRACKER_GAZE_DATA, gaze_data_callback)
t.subscribe_to(tr.EYETRACKER_GAZE_ORIGIN, gaze_data_callback)
time.sleep(1)
#t.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, gaze_data_callback)