import numpy as np
import cv2
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

QUANTIZE_COUNT = 4
VALUE_COUNT = 10

def image_to_ascii(filepath:str):
   bgr_img = cv2.imread(filepath)
   assert bgr_img is not None, f"Could not find input image, searched for {filepath}"

   SCALE = [180.0, 255.0, 255.0]
   hsv_img = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV) / SCALE

   to_circle = np.zeros((*hsv_img.shape[:2],2))
   to_circle[:,:,0] = np.cos(2 * np.pi * hsv_img[:,:,0]) * hsv_img[:,:,1]
   to_circle[:,:,1] = np.sin(2 * np.pi * hsv_img[:,:,0]) * hsv_img[:,:,1]

   kmeans = KMeans(n_clusters=QUANTIZE_COUNT)
   cluster_labels = kmeans.fit_predict(to_circle.reshape(-1,2))

   centers = kmeans.cluster_centers_
   hs_selections = np.zeros((QUANTIZE_COUNT,2))
   hs_selections[:,0] = np.arctan2(centers[:,0], centers[:,1])
   hs_selections[:,1] = np.sqrt(np.square(centers[:,0]), np.square(centers[:,1]))

   if False:
      AXIS_SIZE = 200
      plot = np.zeros((AXIS_SIZE*2, AXIS_SIZE*2, 3))
      for y in range(to_circle.shape[0]):
         for x in range(to_circle.shape[1]):
            px, py = to_circle[y,x]
            tx, ty = AXIS_SIZE+int(px*AXIS_SIZE*0.95), AXIS_SIZE+int(py*AXIS_SIZE*0.95)
            plot[ty,tx] = bgr_img[y,x]
      for i in range(QUANTIZE_COUNT):
         cv2.circle(plot, (AXIS_SIZE+centers[i]*AXIS_SIZE*0.95).astype(np.int32), 2, (0.0, 0.0, 255.0), thickness=6)
      cv2.imwrite("tmp/plot.png", plot)

   if False:
      HEIGHT = 20
      WIDTH  = 200
      hsv_show = np.ones((QUANTIZE_COUNT*HEIGHT,WIDTH,3))
      for i in range(QUANTIZE_COUNT):
         hsv_show[i*HEIGHT:(i+1)*HEIGHT,:,:2] = hs_selections[i]
      hsv_show = (hsv_show * SCALE).astype(np.uint8)
      bgr_show = cv2.cvtColor(hsv_show, cv2.COLOR_HSV2BGR)
      cv2.imwrite("tmp/bgr_show.png", bgr_show)

   print(hs_selections[cluster_labels])
   hsv_img[:,:,:2] = hs_selections[cluster_labels].reshape((*hsv_img.shape[:2],2))
   hsv_img[:,:,2] = (hsv_img[:,:,2] * VALUE_COUNT).astype(int) / VALUE_COUNT
   hsv_img = (hsv_img * SCALE).astype(np.uint8)

   bgr_img = cv2.cvtColor(hsv_img, cv2.COLOR_HSV2BGR)
   cv2.imwrite("tmp/quantized.png", bgr_img)

if __name__ == "__main__":
   image_to_ascii("tmp/image.png")
