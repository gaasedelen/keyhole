import os
import cv2
import pytesseract

import numpy as np

def non_max_suppression_slow(boxes, overlapThresh):
    if len(boxes) == 0:
        return []
    pick = []
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    area = (x2 - x1 + 1) * (y2 - y1 + 1)
    idxs = np.argsort(y2)

    while len(idxs) > 0:
        last = len(idxs) - 1
        i = idxs[last]
        pick.append(i)
        suppress = [last]
        for pos in range(0, last):
            j = idxs[pos]
            xx1 = max(x1[i], x1[j])
            yy1 = max(y1[i], y1[j])
            xx2 = min(x2[i], x2[j])
            yy2 = min(y2[i], y2[j])

            w = max(0, xx2 - xx1 + 1)
            h = max(0, yy2 - yy1 + 1)

            overlap = float(w * h) / area[j]
            if overlap > overlapThresh:
                suppress.append(pos)
        idxs = np.delete(idxs, suppress)
    return boxes[pick]

def do_cv(img_path):

    # load image
    image = cv2.imread(img_path, cv2.IMREAD_COLOR)
    #image = cv2.medianBlur(image,2)

    # convert to greyscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if SHOW_IMG:
        cv2.imshow('GRAY', gray)
        cv2.waitKey()

    (thresh, im_bw) = cv2.threshold(gray, 115, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    #(thresh, im_bw) = cv2.threshold(gray, 115, 255, cv2.THRESH_BINARY)

    if SHOW_IMG or 1:
        cv2.imshow('IMBW', im_bw)
        #cv2.waitKey()

    edged = cv2.Canny(gray, 80, 200)
    if SHOW_IMG:
        cv2.imshow('EDGED', edged)
        cv2.waitKey()

    # dilate / thicken objects
    kernel = np.ones((2,3), np.uint8) 
    edged = cv2.dilate(edged, kernel, iterations=1)
    if SHOW_IMG:
        cv2.imshow('dilated', edged)
        cv2.waitKey()

    cnts, hier = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    #
    # Remove lines & big contours
    #

    # loop over the (sorted) contours
    #cnts = sorted(cnts, key = cv2.contourArea, reverse = True)
    rects = []
    good_cnts = []
    for c in cnts:
        (x, y, w, h) = cv2.boundingRect(c)

        aspect_ratio = float(w)/h
        #print aspect_ratio
        if (aspect_ratio > 3 or aspect_ratio < 0.2) and (h < 8 or w < 8):
            cv2.rectangle(image, (x, y), (x + w, y + h), (0, 0, 255), 1)
            print "BAD RATIO", aspect_ratio
            continue

        if w*h > 6000:
            #cv2.rectangle(image, (x, y), (x + w, y + h), (255, 0, 0), 1)
            print "BAD SIZE", w, h
            continue

        #cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 1)
        good_cnts.append(c)
        rects.append((x,y,x+w,y+h))

    if SHOW_IMG:
        cv2.imshow('CONTOURS', image)
        cv2.waitKey()

    rects = np.array(rects)
    pick = non_max_suppression_slow(rects, 0.3)
    qt_rects = []

    # show selection
    for c in pick:
        (x, y, x2, y2) = c
        if detect_text(image, im_bw, c):
            cv2.rectangle(image, (x, y), (x2, y2), (255, 255, 0), 1)
        else:
            cv2.rectangle(image, (x, y), (x2, y2), (0, 255, 0), 1)

    cv2.imshow('FEATURES', image)
    cv2.waitKey()

def detect_text2(image_rgb, image_bw, rect):
    (x, y, x2, y2) = rect
    w, h = (x2-x, y2-y)
    print pytesseract.image_to_data(image_rgb[y: y + h, x: x + w], output_type=pytesseract.Output.DICT)['text']
    return False

def detect_text(image_rgb, image_bw, rect):
    (x, y, x2, y2) = rect
    w, h = (x2-x, y2-y)

    # top pixels + bottom pixels
    pixels = image_bw[y, x:x2]
    pixels += image_bw[y2-1, x:x2]
    pixels = list(pixels)

    # extract the most frequent color
    bg = max(set(pixels), key = pixels.count)

    # now slice the center of the 'text'
    center_pixels = image_bw[y+(h/2), x:x2]

    # attempt to identify 'gaps' between characters
    all_gaps = [0,w-1]
    for i, pixel in enumerate(center_pixels[1:]):
        tolerance = 1
        for j, v_pixel in enumerate(image_bw[y:y2,x+i]):
            if abs(int(v_pixel) - int(bg)) > 5 and tolerance:
                break
            tolerance -= 1
        else:
            all_gaps.append(i)

    # clean it up
    all_gaps = sorted(set(all_gaps))

    #
    # post-process the character gaps
    #

    sequence = []
    final_gaps = [all_gaps[0]]
    for i, col in enumerate(all_gaps[1:], 1):

        # alias for readability
        last_col = all_gaps[i-1]

        # check if we are in a sequence
        if col == (last_col + 1):
            if sequence:
                sequence.append(col)
            else:
                sequence = [last_col, col]
                final_gaps.pop()
            continue

        # end of a sequence... commit it
        if sequence:
            first, last = sequence[0], sequence[-1]
            middle = (first + last) / 2
            final_gaps.append(middle)
            sequence = []

        # append gap as normal
        final_gaps.append(col)
        
    if sequence:
        first, last = sequence[0], sequence[-1]
        middle = (first + last) / 2
        final_gaps.append(middle)

    final_gaps = final_gaps[1:-1]

    # draw all the gaps
    for i in final_gaps:
        cv2.line(image_rgb, (x+i, y), (x+i, y2), (0,0,255) )
        pass

    return len(final_gaps)
    
    # TODO: ensure all the extracted pixels are of the same color

    avg_width = gaps[0]
    for i in xrange(1, len(gaps)):
        avg_width += abs(gaps[i] - gaps[i-1])
    avg_width /= float((len(gaps)))

    return avg_width > h/8.0

SHOW_IMG = False
PATH = r"C:\Users\markus\hard"

for fname in os.listdir(PATH):
    if "bad" in fname:
        continue
    do_cv(os.path.join(PATH, fname))
    #break