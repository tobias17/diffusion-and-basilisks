from sklearn.cluster import KMeans # type: ignore
import numpy as np
import cv2
from typing import Optional, List

QUANTIZE_COUNT = 16
VALUE_COUNT = 8
ASCII_CODEX = ' .,:;+=#'

CHAR_HEIGHT = 16
CHAR_WIDTH  = 8
CHAR_ASPECT_RATIO = float(CHAR_HEIGHT) / float(CHAR_WIDTH)

SCALE = [180.0, 255.0, 255.0]

def hsv_to_bgr(mat):
   return cv2.cvtColor((mat * SCALE).astype(np.uint8), cv2.COLOR_HSV2BGR)

def image_to_ascii(filepath:str, target_chars_tall:int, target_chars_wide:Optional[int]=None, debug:bool=False) -> List[str]:
   bgr_img = cv2.imread(filepath)
   assert bgr_img is not None, f"Could not find input image, searched for {filepath}"
   shp = bgr_img.shape

   if target_chars_wide is None:
      target_chars_wide = int(target_chars_tall * (shp[1] / shp[0]) * CHAR_ASPECT_RATIO)
      if debug:
         print(f"Computed {target_chars_wide} chars wide (and {target_chars_tall} chars tall)")
   y_step = shp[0] / target_chars_tall
   x_step = shp[1] / target_chars_wide

   orig_hsv_img = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV) / SCALE

   to_circle = np.zeros((*orig_hsv_img.shape[:2],2))
   to_circle[:,:,0] = np.cos(2*np.pi * orig_hsv_img[:,:,0]) * orig_hsv_img[:,:,1]
   to_circle[:,:,1] = np.sin(2*np.pi * orig_hsv_img[:,:,0]) * orig_hsv_img[:,:,1]

   kmeans = KMeans(n_clusters=QUANTIZE_COUNT)
   cluster_labels = kmeans.fit_predict(to_circle.reshape(-1,2))
   img_clusters = cluster_labels.reshape(orig_hsv_img.shape[:2])

   centers = kmeans.cluster_centers_
   hs_selections = np.zeros((QUANTIZE_COUNT,2))
   hs_selections[:,0] = np.arctan2(centers[:,1], centers[:,0]) / (2*np.pi)
   hs_selections[:,0] = np.where(hs_selections[:,0] < 0.0, hs_selections[:,0] + 1.0, hs_selections[:,0])
   hs_selections[:,1] = np.sqrt(np.square(centers[:,0]), np.square(centers[:,1])) * 1.1
   hs_selections[:,1] = np.where(hs_selections[:,1] > 1.0, 1.0, hs_selections[:,1])

   if debug:
      AXIS_SIZE = 200
      plot_hsv = np.zeros((AXIS_SIZE*2, AXIS_SIZE*2, 3))
      for y in range(to_circle.shape[0]):
         for x in range(to_circle.shape[1]):
            px, py = to_circle[y,x]
            tx, ty = AXIS_SIZE+int(px*AXIS_SIZE*0.95), AXIS_SIZE+int(py*AXIS_SIZE*0.95)
            plot_hsv[ty,tx,:2] = orig_hsv_img[y,x,:2]
            plot_hsv[ty,tx,2] = 1.0
      plot_bgr = hsv_to_bgr(plot_hsv)
      for i in range(QUANTIZE_COUNT):
         cv2.circle(plot_bgr, (AXIS_SIZE+centers[i]*AXIS_SIZE*0.95).astype(np.int32), 2, (0.0, 0.0, 255.0), thickness=6)
      cv2.imwrite("tmp/plot.png", plot_bgr)

      HEIGHT = 20
      WIDTH  = 200
      hsv_show = np.ones((QUANTIZE_COUNT*HEIGHT,WIDTH,3))
      for i in range(QUANTIZE_COUNT):
         hsv_show[i*HEIGHT:(i+1)*HEIGHT,:,:2] = hs_selections[i]
      hsv_show = (hsv_show * SCALE).astype(np.uint8)
      bgr_show = cv2.cvtColor(hsv_show, cv2.COLOR_HSV2BGR)
      cv2.imwrite("tmp/bgr_show.png", bgr_show)

   hsv_img = orig_hsv_img.copy()
   hsv_img[:,:,:2] = hs_selections[cluster_labels].reshape((*orig_hsv_img.shape[:2],2))
   hsv_full = hsv_img.copy()
   hsv_full[:,:,2] = 0.6

   hsv_selections = np.ones((QUANTIZE_COUNT,3)) * 0.95
   hsv_selections[:,:2] = hs_selections

   if debug:
      cv2.imwrite("tmp/quantized.png", hsv_to_bgr(hsv_img))
      cv2.imwrite("tmp/quantized_full.png", hsv_to_bgr(hsv_full))

   small_patch_v = np.zeros((target_chars_tall,target_chars_wide))
   small_patch_hsv = np.ones((target_chars_tall,target_chars_wide,3))
   patched_hsv = np.zeros(shp)
   for yi in range(target_chars_tall):
      for xi in range(target_chars_wide):
         xs, xe = int(xi*x_step), int((xi+1)*x_step)
         ys, ye = int(yi*y_step), int((yi+1)*y_step)
         max_weight, max_index = 0, 0
         for i in range(QUANTIZE_COUNT):
            index_weight = np.where(img_clusters[ys:ye,xs:xe] == i, hsv_img[ys:ye,xs:xe,1], 0).sum()
            if index_weight > max_weight:
               max_weight = index_weight
               max_index = i
         # mode = stats.mode(img_clusters[ys:ye,xs:xe].flatten()).mode
         patched_hsv[ys:ye,xs:xe,:2] = hs_selections[max_index]
         patched_hsv[ys:ye,xs:xe,2] = hsv_img[ys:ye,xs:xe,2].mean()
         small_patch_hsv[yi,xi,:2] = hs_selections[max_index]
         small_patch_v[yi,xi] = hsv_img[ys:ye,xs:xe,2].mean()
   if debug:
      cv2.imwrite("tmp/patched.png", hsv_to_bgr(patched_hsv))
   small_patch_bgr = hsv_to_bgr(small_patch_hsv)

   lines = []
   for y in range(target_chars_tall):
      text = "\033[48;2;10;10;10m"
      pb, pg, pr = None, None, None
      for x in range(target_chars_wide):
         b, g, r = small_patch_bgr[y,x]
         idx = max(0, min(len(ASCII_CODEX)-1, int(small_patch_v[y,x] * len(ASCII_CODEX))))
         c = ASCII_CODEX[idx]
         if c == ' ' or ((pb is not None) and (r == pr) and (g == pg) and (r == pr)):
            text += c
         else:
            text += f"\033[38;2;{r};{g};{b}m{c}"
            pb, pg, pr = b, g, r
      text += "\033[0m"
      lines.append(text)
   return lines

if __name__ == "__main__":
   import argparse
   parser = argparse.ArgumentParser()
   parser.add_argument('--file', type=str, default='tmp/image.png')
   args = parser.parse_args()

   lines = image_to_ascii(args.file, 60, debug=True)
   for line in lines:
      print(line)
