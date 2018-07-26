import numpy as np
from keras.applications.nasnet import NASNetLarge, decode_predictions, preprocess_input
from keras.preprocessing import image

img_mapping = {'cars': {'sports_car', 'passenger_car', 'convertible', 'minivan', 'limousine', 
                        'moving_van', 'car_mirror', 'police_van', 'ambulance'},
               'store front': {'tobacco_shop', 'toyshop', 'bakery', 'restaurant', 
                               'grocery_store', 'cinema', 'library', 'barbershop'},
               'street signs': {'street_sign'},
               'bus': {'trailer_truck', 'tow_truck', 'moving_van', 'school_bus', 'trolleybus', 'recreational_vehicle'},
               'roads': {'worm_fence'},
               'traffic lights': {'traffic_light'}}

NASNet = NASNetLarge(include_top=True, weights='models/NASNet-large.h5', classes=1000)

def predict(images, labels, threshold):
    num_rows = len(images)
    num_cols = len(images[0]) 
    predictions = []
    for row in range(num_rows):
        for col in range(num_cols):          
            curr_image = images[row][col]
            img_data = np.expand_dims(curr_image, axis=0)
            img_data = preprocess_input(img_data)

            y_prob = NASNet.predict(img_data)
            y_pred = decode_predictions(y_prob, top=5)[0]
            
            print(str(row) + str(col), end=' ')
            for pred in y_pred:
                print(pred[1] + ': ' + str(pred[2]), end=', ')
            print('\n')

            for label in labels:
                for pred in y_pred:
                    if pred[1] in img_mapping[label] and pred[2] > threshold:
                        predictions.append((row, col))
                        break
    return predictions