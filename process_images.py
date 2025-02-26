from sklearn.cluster import KMeans
from scipy import stats
import numpy as np
import cv2, sys
from typing import Optional, List

QUANTIZE_COUNT = 16
VALUE_COUNT = 8
ASCII_CODEX = ' .,:;+=#'

CHAR_HEIGHT = 16
CHAR_WIDTH  = 8
CHAR_ASPECT_RATIO = float(CHAR_HEIGHT) / float(CHAR_WIDTH)

SCALE = [180.0, 255.0, 255.0]

def color(text:str, r:int, g:int, b:int) -> str:
   return f"\033[38;2;{r};{g};{b}m{text}\033[0m"

def hsv_to_bgr(mat):
   return cv2.cvtColor((mat * SCALE).astype(np.uint8), cv2.COLOR_HSV2BGR)

def diff_of_gaus(gray, sigma1=1.6, sigma2=1.2, threshold=0.05, kernel_size:int=2):
   blur1 = cv2.GaussianBlur(gray, (0,0), sigmaX=sigma1)
   blur2 = cv2.GaussianBlur(gray, (0,0), sigmaX=sigma2)
   dog = blur1 - blur2
   dog_norm = cv2.normalize(np.abs(dog), None, 0, 255, cv2.NORM_MINMAX) # type: ignore

   keypoints = dog_norm > (255 * threshold)

   result = np.zeros_like(gray)
   result[keypoints] = 255

   kernel = np.ones((kernel_size, kernel_size), np.uint8)
   eroded = cv2.erode(result, kernel, iterations=2)
   return eroded

class DirData:
   amnt: float
   def __init__(self, char, in_mat):
      self.char = char
      self.in_mat = in_mat

def apply_sobel_filter(img, w:int, h:int, x_step:float, y_step:float, kernel_size=3, debug=False):
   gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
   dog = diff_of_gaus(gray)
   if debug:
      cv2.imwrite(f"tmp/gray.png", gray)
      cv2.imwrite(f"tmp/dog.png", dog)

   x_grad = cv2.Sobel(dog, cv2.CV_32F, 1, 0, ksize=kernel_size)
   y_grad = cv2.Sobel(dog, cv2.CV_32F, 0, 1, ksize=kernel_size)
   grad_dir = np.arctan2(y_grad, x_grad) * 180 / np.pi
   # grad_mag = np.sqrt(np.square(x_grad) + np.square(y_grad))
   # grad_mag = cv2.normalize(grad_mag, None, 0, 255, cv2.NORM_MINMAX) # type: ignore

   x_grad_save = x_grad / 8 + 128
   y_grad_save = y_grad / 8 + 128

   if debug:
      cv2.imwrite("tmp/x_grad.png", x_grad_save.astype(np.uint8))
      cv2.imwrite("tmp/y_grad.png", y_grad_save.astype(np.uint8))
      # cv2.imwrite("tmp/grad_mag.png", grad_mag.astype(np.uint8))

   threshold = 10.0

   is_set = np.zeros_like(img)

   amnts = np.zeros((h,w))
   chars = np.full((h,w), fill_value=' ', dtype='<U1')
   for y in range(h):
      for x in range(w):
         ys, ye = int(y*y_step), int((y+1)*y_step)
         xs, xe = int(x*x_step), int((x+1)*x_step)
         patch_mag = dog[ys:ye, xs:xe]
         patch_dir = grad_dir[ys:ye, xs:xe]

         dir_datas = [
            DirData('-', ((patch_dir >=  -22.5) & (patch_dir <   22.5)) | ((patch_dir >= 157.5) | (patch_dir < -157.5))),
            DirData('|', ((patch_dir >= -112.5) & (patch_dir <  -67.5)) | ((patch_dir >=  67.5) & (patch_dir <  112.5))),
            DirData('/', ((patch_dir >= -157.5) & (patch_dir < -112.5)) | ((patch_dir >=  22.5) & (patch_dir <   67.5))),
            DirData('/', ((patch_dir >=  -67.5) & (patch_dir <  -22.5)) | ((patch_dir >= 112.5) & (patch_dir <  157.5))),
         ]
         size = patch_mag.shape[0] * patch_mag.shape[1]
         total_amnt = np.sum(patch_mag)
         for data in dir_datas:
            # data.amnt = np.sum(patch_mag[data.in_mat]) / size
            data.amnt = np.sum(patch_mag[data.in_mat])**2 / (total_amnt * size)

         max_amnt, max_char = threshold, ' '
         for data in dir_datas:
            if data.amnt > max_amnt:
               max_amnt = data.amnt
               max_char = data.char
         amnts[y,x] = max_amnt
         chars[y,x] = max_char

         if max_char != ' ':
            is_set[ys:ye, xs:xe] = 255
   
   if debug:
      cv2.imwrite("tmp/is_set.png", is_set.astype(np.uint8))

   return chars

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

   # chars = apply_sobel_filter(bgr_img, target_chars_wide, target_chars_tall, x_step, y_step, debug=debug)

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
   # hsv_img[:,:,2] = (hsv_img[:,:,2] * VALUE_COUNT).astype(int) / VALUE_COUNT
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
         # c = chars[y,x]
         # if c == ' ':
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
