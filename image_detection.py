import numpy as np
import os
import tensorflow as tf

from object_detection.utils import label_map_util
from object_detection.utils import ops as utils_ops
from object_detection.utils import visualization_utils as vis_util
from PIL import Image

MODEL_NAME = 'faster_rcnn_resnet50'
OBJECT_DETECTION_PATH = 'object_detection'

# Path to the frozen detection graph used for object detection.
PATH_TO_FROZEN_GRAPH = OBJECT_DETECTION_PATH + '/' + MODEL_NAME + '/frozen_inference_graph.pb'

# Path to the class labels mapping file.
PATH_TO_LABELS = os.path.join(OBJECT_DETECTION_PATH, 'data', 'mscoco_label_map.pbtxt')

NUM_CLASSES = 90
PREDICTION_THRESHOLD = 0.5
CLASS_LABELS_MAP = {'bicycle': {'bicycles'},
                    'truck': {'cars'},
                    'car': {'cars'},
                    'motorcycle': {'motocycles'},
                    'bus': {'bus'},
                    'traffic light': {'traffic lights'},
                    'fire hydrant': {'a fire hydrant', 'fire hydrants'}}

label_map = label_map_util.load_labelmap(PATH_TO_LABELS)
categories = label_map_util.convert_label_map_to_categories(label_map, max_num_classes=NUM_CLASSES, use_display_name=True)
category_index = label_map_util.create_category_index(categories)

detection_graph = tf.Graph()
with detection_graph.as_default():
  od_graph_def = tf.GraphDef()
  with tf.gfile.GFile(PATH_TO_FROZEN_GRAPH, 'rb') as fid:
    serialized_graph = fid.read()
    od_graph_def.ParseFromString(serialized_graph)
    tf.import_graph_def(od_graph_def, name='')

def load_image_into_numpy_array(image):
  (im_width, im_height) = image.size
  return np.array(image.getdata()).reshape(
      (im_height, im_width, 3)).astype(np.uint8)

def run_inference_for_single_image(image, graph):
  with graph.as_default():
    with tf.Session() as sess:
      # Get handles to input and output tensors
      ops = tf.get_default_graph().get_operations()
      all_tensor_names = {output.name for op in ops for output in op.outputs}
      tensor_dict = {}
      for key in [
          'num_detections', 'detection_boxes', 'detection_scores',
          'detection_classes', 'detection_masks'
      ]:
        tensor_name = key + ':0'
        if tensor_name in all_tensor_names:
          tensor_dict[key] = tf.get_default_graph().get_tensor_by_name(
              tensor_name)
      if 'detection_masks' in tensor_dict:
        # The following processing is only for single image
        detection_boxes = tf.squeeze(tensor_dict['detection_boxes'], [0])
        detection_masks = tf.squeeze(tensor_dict['detection_masks'], [0])
        # Reframe is required to translate mask from box coordinates to image coordinates and fit the image size.
        real_num_detection = tf.cast(tensor_dict['num_detections'][0], tf.int32)
        detection_boxes = tf.slice(detection_boxes, [0, 0], [real_num_detection, -1])
        detection_masks = tf.slice(detection_masks, [0, 0, 0], [real_num_detection, -1, -1])
        detection_masks_reframed = utils_ops.reframe_box_masks_to_image_masks(
            detection_masks, detection_boxes, image.shape[0], image.shape[1])
        detection_masks_reframed = tf.cast(
            tf.greater(detection_masks_reframed, 0.5), tf.uint8)
        # Follow the convention by adding back the batch dimension
        tensor_dict['detection_masks'] = tf.expand_dims(
            detection_masks_reframed, 0)
      image_tensor = tf.get_default_graph().get_tensor_by_name('image_tensor:0')

      # Run inference
      output_dict = sess.run(tensor_dict,
                             feed_dict={image_tensor: np.expand_dims(image, 0)})

      # all outputs are float32 numpy arrays, so convert types as appropriate
      output_dict['num_detections'] = int(output_dict['num_detections'][0])
      output_dict['detection_classes'] = output_dict[
          'detection_classes'][0].astype(np.uint8)
      output_dict['detection_boxes'] = output_dict['detection_boxes'][0]
      output_dict['detection_scores'] = output_dict['detection_scores'][0]
      if 'detection_masks' in output_dict:
        output_dict['detection_masks'] = output_dict['detection_masks'][0]
  return output_dict

def calculate_tiles(predictions, x_min, y_min, x_max, y_max, width, height, overlap):
    start_row = y_min // height
    end_row = y_max // height if overlap else start_row
    start_col = x_min // width
    end_col = x_max // width if overlap else start_col

    for row in range(start_row, end_row + 1):
        for col in range(start_col, end_col + 1):   
            if (row, col) not in predictions:
                predictions.append((row, col))

def predict(image_arr, labels, rows, cols):
    output_dict = run_inference_for_single_image(image_arr, detection_graph)
    height, width = image_arr.shape[0], image_arr.shape[1]
    box_width = width // cols
    box_height = height // rows
    category_index = label_map_util.create_category_index(categories)
    predictions = []
    
    for i in range(len(output_dict['detection_boxes'])):
        if output_dict['detection_scores'][i] > PREDICTION_THRESHOLD:
            class_name = category_index[output_dict['detection_classes'][i]]['name']
            for label in labels:
                label_mappings = CLASS_LABELS_MAP.get(class_name, class_name)
                if label in label_mappings:
                    calculate_tiles(predictions,
                                    int(width * output_dict['detection_boxes'][i][1]),
                                    int(height * output_dict['detection_boxes'][i][0]),
                                    int(width * output_dict['detection_boxes'][i][3]),
                                    int(height * output_dict['detection_boxes'][i][2]),
                                    box_width,
                                    box_height,
                                    rows == 4 and cols == 4)
                    break

            print("{class: %s, prediction: %s, boundingbox: %i,%i,%i,%i,%i,%i}"
                    % (class_name,
                        output_dict['detection_scores'][i],
                        width,
                        height,
                        int(width * output_dict['detection_boxes'][i][1]),  
                        int(height * output_dict['detection_boxes'][i][0]),
                        int(width * output_dict['detection_boxes'][i][3]),
                        int(height * output_dict['detection_boxes'][i][2])
                        ))
    return predictions