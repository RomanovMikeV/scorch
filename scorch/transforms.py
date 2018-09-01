from __future__ import division

import numpy
import skimage.transform
import torch
import random

import torch
import math
import random
from PIL import Image, ImageOps, ImageEnhance
try:
    import accimage
except ImportError:
    accimage = None
import numpy as np
import numbers
import types
import collections
import warnings
import skimage.transform
import numpy


def _is_pil_image(img):
    if accimage is not None:
        return isinstance(img, (Image.Image, accimage.Image))
    else:
        return isinstance(img, Image.Image)


def _is_tensor_image(img):
    return torch.is_tensor(img) and img.ndimension() == 3


def _is_numpy_image(img):
    return isinstance(img, np.ndarray) and (img.ndim in {2, 3})


def to_tensor(pic):
    """Convert a ``PIL Image`` or ``numpy.ndarray`` to tensor.
    See ``ToTensor`` for more details.
    Args:
        pic (PIL Image or numpy.ndarray): Image to be converted to tensor.
    Returns:
        Tensor: Converted image.
    """
    if not(_is_pil_image(pic) or _is_numpy_image(pic)):
        raise TypeError('pic should be PIL Image or ndarray. Got {}'.format(type(pic)))

    if isinstance(pic, np.ndarray):
        # handle numpy array
        img = torch.from_numpy(pic.transpose((2, 0, 1)))
        # backward compatibility
        return img.float().div(255)

    if accimage is not None and isinstance(pic, accimage.Image):
        nppic = np.zeros([pic.channels, pic.height, pic.width], dtype=np.float32)
        pic.copyto(nppic)
        return torch.from_numpy(nppic)

    # handle PIL Image
    if pic.mode == 'I':
        img = torch.from_numpy(np.array(pic, np.int32, copy=False))
    elif pic.mode == 'I;16':
        img = torch.from_numpy(np.array(pic, np.int16, copy=False))
    else:
        img = torch.ByteTensor(torch.ByteStorage.from_buffer(pic.tobytes()))
    # PIL image mode: 1, L, P, I, F, RGB, YCbCr, RGBA, CMYK
    if pic.mode == 'YCbCr':
        nchannel = 3
    elif pic.mode == 'I;16':
        nchannel = 1
    else:
        nchannel = len(pic.mode)
    img = img.view(pic.size[1], pic.size[0], nchannel)
    # put it from HWC to CHW format
    # yikes, this transpose takes 80% of the loading time/CPU
    img = img.transpose(0, 1).transpose(0, 2).contiguous()
    if isinstance(img, torch.ByteTensor):
        return img.float().div(255)
    else:
        return img


def to_pil_image(pic, mode=None):
    """Convert a tensor or an ndarray to PIL Image.
    See :class:`~torchvision.transforms.ToPIlImage` for more details.
    Args:
        pic (Tensor or numpy.ndarray): Image to be converted to PIL Image.
        mode (`PIL.Image mode`_): color space and pixel depth of input data (optional).
    .. _PIL.Image mode: http://pillow.readthedocs.io/en/3.4.x/handbook/concepts.html#modes
    Returns:
        PIL Image: Image converted to PIL Image.
    """
    if not(_is_numpy_image(pic) or _is_tensor_image(pic)):
        raise TypeError('pic should be Tensor or ndarray. Got {}.'.format(type(pic)))

    npimg = pic
    if isinstance(pic, torch.FloatTensor):
        pic = pic.mul(255).byte()
    if torch.is_tensor(pic):
        npimg = np.transpose(pic.numpy(), (1, 2, 0))

    if not isinstance(npimg, np.ndarray):
        raise TypeError('Input pic must be a torch.Tensor or NumPy ndarray, ' +
                        'not {}'.format(type(npimg)))

    if npimg.shape[2] == 1:
        expected_mode = None
        npimg = npimg[:, :, 0]
        if npimg.dtype == np.uint8:
            expected_mode = 'L'
        if npimg.dtype == np.int16:
            expected_mode = 'I;16'
        if npimg.dtype == np.int32:
            expected_mode = 'I'
        elif npimg.dtype == np.float32:
            expected_mode = 'F'
        if mode is not None and mode != expected_mode:
            raise ValueError("Incorrect mode ({}) supplied for input type {}. Should be {}"
                             .format(mode, np.dtype, expected_mode))
        mode = expected_mode

    elif npimg.shape[2] == 4:
        permitted_4_channel_modes = ['RGBA', 'CMYK']
        if mode is not None and mode not in permitted_4_channel_modes:
            raise ValueError("Only modes {} are supported for 4D inputs".format(permitted_4_channel_modes))

        if mode is None and npimg.dtype == np.uint8:
            mode = 'RGBA'
    else:
        permitted_3_channel_modes = ['RGB', 'YCbCr', 'HSV']
        if mode is not None and mode not in permitted_3_channel_modes:
            raise ValueError("Only modes {} are supported for 3D inputs".format(permitted_3_channel_modes))
        if mode is None and npimg.dtype == np.uint8:
            mode = 'RGB'

    if mode is None:
        raise TypeError('Input type {} is not supported'.format(npimg.dtype))

    return Image.fromarray(npimg, mode=mode)


def normalize(tensor, mean, std):
    """Normalize a tensor image with mean and standard deviation.
    See ``Normalize`` for more details.
    Args:
        tensor (Tensor): Tensor image of size (C, H, W) to be normalized.
        mean (sequence): Sequence of means for each channel.
        std (sequence): Sequence of standard deviations for each channely.
    Returns:
        Tensor: Normalized Tensor image.
    """
    if not _is_tensor_image(tensor):
        raise TypeError('tensor is not a torch image.')
    # TODO: make efficient
    for t, m, s in zip(tensor, mean, std):
        t.sub_(m).div_(s)
    return tensor


def resize(img, size, interpolation=Image.BILINEAR):
    """Resize the input PIL Image to the given size.
    Args:
        img (PIL Image): Image to be resized.
        size (sequence or int): Desired output size. If size is a sequence like
            (h, w), the output size will be matched to this. If size is an int,
            the smaller edge of the image will be matched to this number maintaing
            the aspect ratio. i.e, if height > width, then image will be rescaled to
            (size * height / width, size)
        interpolation (int, optional): Desired interpolation. Default is
            ``PIL.Image.BILINEAR``
    Returns:
        PIL Image: Resized image.
    """
    if not _is_pil_image(img):
        raise TypeError('img should be PIL Image. Got {}'.format(type(img)))
    if not (isinstance(size, int) or (isinstance(size, collections.Iterable) and len(size) == 2)):
        raise TypeError('Got inappropriate size arg: {}'.format(size))

    if isinstance(size, int):
        w, h = img.size
        if (w <= h and w == size) or (h <= w and h == size):
            return img
        if w < h:
            ow = size
            oh = int(size * h / w)
            return img.resize((ow, oh), interpolation)
        else:
            oh = size
            ow = int(size * w / h)
            return img.resize((ow, oh), interpolation)
    else:
        return img.resize(size[::-1], interpolation)


def scale(*args, **kwargs):
    warnings.warn("The use of the transforms.Scale transform is deprecated, " +
                  "please use transforms.Resize instead.")
    return resize(*args, **kwargs)


def pad(img, padding, fill=0):
    """Pad the given PIL Image on all sides with the given "pad" value.
    Args:
        img (PIL Image): Image to be padded.
        padding (int or tuple): Padding on each border. If a single int is provided this
            is used to pad all borders. If tuple of length 2 is provided this is the padding
            on left/right and top/bottom respectively. If a tuple of length 4 is provided
            this is the padding for the left, top, right and bottom borders
            respectively.
        fill: Pixel fill value. Default is 0. If a tuple of
            length 3, it is used to fill R, G, B channels respectively.
    Returns:
        PIL Image: Padded image.
    """
    if not _is_pil_image(img):
        raise TypeError('img should be PIL Image. Got {}'.format(type(img)))

    if not isinstance(padding, (numbers.Number, tuple)):
        raise TypeError('Got inappropriate padding arg')
    if not isinstance(fill, (numbers.Number, str, tuple)):
        raise TypeError('Got inappropriate fill arg')

    if isinstance(padding, collections.Sequence) and len(padding) not in [2, 4]:
        raise ValueError("Padding must be an int or a 2, or 4 element tuple, not a " +
                         "{} element tuple".format(len(padding)))

    return ImageOps.expand(img, border=padding, fill=fill)


def crop(img, i, j, h, w):
    """Crop the given PIL Image.
    Args:
        img (PIL Image): Image to be cropped.
        i: Upper pixel coordinate.
        j: Left pixel coordinate.
        h: Height of the cropped image.
        w: Width of the cropped image.
    Returns:
        PIL Image: Cropped image.
    """
    if not _is_pil_image(img):
        raise TypeError('img should be PIL Image. Got {}'.format(type(img)))

    return img.crop((j, i, j + w, i + h))


def resized_crop(img, i, j, h, w, size, interpolation=Image.BILINEAR):
    """Crop the given PIL Image and resize it to desired size.
    Notably used in RandomResizedCrop.
    Args:
        img (PIL Image): Image to be cropped.
        i: Upper pixel coordinate.
        j: Left pixel coordinate.
        h: Height of the cropped image.
        w: Width of the cropped image.
        size (sequence or int): Desired output size. Same semantics as ``scale``.
        interpolation (int, optional): Desired interpolation. Default is
            ``PIL.Image.BILINEAR``.
    Returns:
        PIL Image: Cropped image.
    """
    assert _is_pil_image(img), 'img should be PIL Image'
    img = crop(img, i, j, h, w)
    img = resize(img, size, interpolation)
    return img


def hflip(img):
    """Horizontally flip the given PIL Image.
    Args:
        img (PIL Image): Image to be flipped.
    Returns:
        PIL Image:  Horizontall flipped image.
    """
    if not _is_pil_image(img):
        raise TypeError('img should be PIL Image. Got {}'.format(type(img)))

    return img.transpose(Image.FLIP_LEFT_RIGHT)


def vflip(img):
    """Vertically flip the given PIL Image.
    Args:
        img (PIL Image): Image to be flipped.
    Returns:
        PIL Image:  Vertically flipped image.
    """
    if not _is_pil_image(img):
        raise TypeError('img should be PIL Image. Got {}'.format(type(img)))

    return img.transpose(Image.FLIP_TOP_BOTTOM)


def five_crop(img, size):
    """Crop the given PIL Image into four corners and the central crop.
    .. Note::
        This transform returns a tuple of images and there may be a
        mismatch in the number of inputs and targets your ``Dataset`` returns.
    Args:
       size (sequence or int): Desired output size of the crop. If size is an
           int instead of sequence like (h, w), a square crop (size, size) is
           made.
    Returns:
        tuple: tuple (tl, tr, bl, br, center) corresponding top left,
            top right, bottom left, bottom right and center crop.
    """
    if isinstance(size, numbers.Number):
        size = (int(size), int(size))
    else:
        assert len(size) == 2, "Please provide only two dimensions (h, w) for size."

    w, h = img.size
    crop_h, crop_w = size
    if crop_w > w or crop_h > h:
        raise ValueError("Requested crop size {} is bigger than input size {}".format(size,
                                                                                      (h, w)))
    tl = img.crop((0, 0, crop_w, crop_h))
    tr = img.crop((w - crop_w, 0, w, crop_h))
    bl = img.crop((0, h - crop_h, crop_w, h))
    br = img.crop((w - crop_w, h - crop_h, w, h))
    center = CenterCrop((crop_h, crop_w))(img)
    return (tl, tr, bl, br, center)


def ten_crop(img, size, vertical_flip=False):
    """Crop the given PIL Image into four corners and the central crop plus the
       flipped version of these (horizontal flipping is used by default).
    .. Note::
        This transform returns a tuple of images and there may be a
        mismatch in the number of inputs and targets your ``Dataset`` returns.
       Args:
           size (sequence or int): Desired output size of the crop. If size is an
               int instead of sequence like (h, w), a square crop (size, size) is
               made.
           vertical_flip (bool): Use vertical flipping instead of horizontal
        Returns:
            tuple: tuple (tl, tr, bl, br, center, tl_flip, tr_flip, bl_flip,
                br_flip, center_flip) corresponding top left, top right,
                bottom left, bottom right and center crop and same for the
                flipped image.
    """
    if isinstance(size, numbers.Number):
        size = (int(size), int(size))
    else:
        assert len(size) == 2, "Please provide only two dimensions (h, w) for size."

    first_five = five_crop(img, size)

    if vertical_flip:
        img = vflip(img)
    else:
        img = hflip(img)

    second_five = five_crop(img, size)
    return first_five + second_five


def adjust_brightness(img, brightness_factor):
    """Adjust brightness of an Image.
    Args:
        img (PIL Image): PIL Image to be adjusted.
        brightness_factor (float):  How much to adjust the brightness. Can be
            any non negative number. 0 gives a black image, 1 gives the
            original image while 2 increases the brightness by a factor of 2.
    Returns:
        PIL Image: Brightness adjusted image.
    """
    if not _is_pil_image(img):
        raise TypeError('img should be PIL Image. Got {}'.format(type(img)))

    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(brightness_factor)
    return img


def adjust_contrast(img, contrast_factor):
    """Adjust contrast of an Image.
    Args:
        img (PIL Image): PIL Image to be adjusted.
        contrast_factor (float): How much to adjust the contrast. Can be any
            non negative number. 0 gives a solid gray image, 1 gives the
            original image while 2 increases the contrast by a factor of 2.
    Returns:
        PIL Image: Contrast adjusted image.
    """
    if not _is_pil_image(img):
        raise TypeError('img should be PIL Image. Got {}'.format(type(img)))

    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(contrast_factor)
    return img


def adjust_saturation(img, saturation_factor):
    """Adjust color saturation of an image.
    Args:
        img (PIL Image): PIL Image to be adjusted.
        saturation_factor (float):  How much to adjust the saturation. 0 will
            give a black and white image, 1 will give the original image while
            2 will enhance the saturation by a factor of 2.
    Returns:
        PIL Image: Saturation adjusted image.
    """
    if not _is_pil_image(img):
        raise TypeError('img should be PIL Image. Got {}'.format(type(img)))

    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(saturation_factor)
    return img


def adjust_hue(img, hue_factor):
    """Adjust hue of an image.
    The image hue is adjusted by converting the image to HSV and
    cyclically shifting the intensities in the hue channel (H).
    The image is then converted back to original image mode.
    `hue_factor` is the amount of shift in H channel and must be in the
    interval `[-0.5, 0.5]`.
    See https://en.wikipedia.org/wiki/Hue for more details on Hue.
    Args:
        img (PIL Image): PIL Image to be adjusted.
        hue_factor (float):  How much to shift the hue channel. Should be in
            [-0.5, 0.5]. 0.5 and -0.5 give complete reversal of hue channel in
            HSV space in positive and negative direction respectively.
            0 means no shift. Therefore, both -0.5 and 0.5 will give an image
            with complementary colors while 0 gives the original image.
    Returns:
        PIL Image: Hue adjusted image.
    """
    if not(-0.5 <= hue_factor <= 0.5):
        raise ValueError('hue_factor is not in [-0.5, 0.5].'.format(hue_factor))

    if not _is_pil_image(img):
        raise TypeError('img should be PIL Image. Got {}'.format(type(img)))

    input_mode = img.mode
    if input_mode in {'L', '1', 'I', 'F'}:
        return img

    h, s, v = img.convert('HSV').split()

    np_h = np.array(h, dtype=np.uint8)
    # uint8 addition take cares of rotation across boundaries
    with np.errstate(over='ignore'):
        np_h += np.uint8(hue_factor * 255)
    h = Image.fromarray(np_h, 'L')

    img = Image.merge('HSV', (h, s, v)).convert(input_mode)
    return img


def adjust_gamma(img, gamma, gain=1):
    """Perform gamma correction on an image.
    Also known as Power Law Transform. Intensities in RGB mode are adjusted
    based on the following equation:
        I_out = 255 * gain * ((I_in / 255) ** gamma)
    See https://en.wikipedia.org/wiki/Gamma_correction for more details.
    Args:
        img (PIL Image): PIL Image to be adjusted.
        gamma (float): Non negative real number. gamma larger than 1 make the
            shadows darker, while gamma smaller than 1 make dark regions
            lighter.
        gain (float): The constant multiplier.
    """
    if not _is_pil_image(img):
        raise TypeError('img should be PIL Image. Got {}'.format(type(img)))

    if gamma < 0:
        raise ValueError('Gamma should be a non-negative real number')

    input_mode = img.mode
    img = img.convert('RGB')

    np_img = np.array(img, dtype=np.float32)
    np_img = 255 * gain * ((np_img / 255) ** gamma)
    np_img = np.uint8(np.clip(np_img, 0, 255))

    img = Image.fromarray(np_img, 'RGB').convert(input_mode)
    return img


class Compose(object):
    """Composes several transforms together.
    Args:
        transforms (list of ``Transform`` objects): list of transforms to compose.
    Example:
        >>> transforms.Compose([
        >>>     transforms.CenterCrop(10),
        >>>     transforms.ToTensor(),
        >>> ])
    """

    def __init__(self, transforms):
        self.transforms = transforms

    def seed(self):
        for transform in self.transforms:
            transform.seed()

    def __call__(self, img):

        for t in self.transforms:
            img = t(img)
        return img


class ToTensor(object):
    """Convert a ``PIL Image`` or ``numpy.ndarray`` to tensor.
    Converts a PIL Image or numpy.ndarray (H x W x C) in the range
    [0, 255] to a torch.FloatTensor of shape (C x H x W) in the range [0.0, 1.0].
    """

    def seed(self):
        pass

    def __call__(self, pic):
        """
        Args:
            pic (PIL Image or numpy.ndarray): Image to be converted to tensor.
        Returns:
            Tensor: Converted image.
        """
        return to_tensor(pic)


class ToPILImage(object):
    """Convert a tensor or an ndarray to PIL Image.
    Converts a torch.*Tensor of shape C x H x W or a numpy ndarray of shape
    H x W x C to a PIL Image while preserving the value range.
    Args:
        mode (`PIL.Image mode`_): color space and pixel depth of input data (optional).
            If ``mode`` is ``None`` (default) there are some assumptions made about the input data:
            1. If the input has 3 channels, the ``mode`` is assumed to be ``RGB``.
            2. If the input has 4 channels, the ``mode`` is assumed to be ``RGBA``.
            3. If the input has 1 channel, the ``mode`` is determined by the data type (i,e,
            ``int``, ``float``, ``short``).
    .. _PIL.Image mode: http://pillow.readthedocs.io/en/3.4.x/handbook/concepts.html#modes
    """
    def __init__(self, mode=None):
        self.mode = mode

    def seed(self):
        pass

    def __call__(self, pic):
        """
        Args:
            pic (Tensor or numpy.ndarray): Image to be converted to PIL Image.
        Returns:
            PIL Image: Image converted to PIL Image.
        """
        return to_pil_image(pic, self.mode)


class Normalize(object):
    """Normalize an tensor image with mean and standard deviation.
    Given mean: ``(M1,...,Mn)`` and std: ``(M1,..,Mn)`` for ``n`` channels, this transform
    will normalize each channel of the input ``torch.*Tensor`` i.e.
    ``input[channel] = (input[channel] - mean[channel]) / std[channel]``
    Args:
        mean (sequence): Sequence of means for each channel.
        std (sequence): Sequence of standard deviations for each channel.
    """

    def __init__(self, mean, std):
        self.mean = mean
        self.std = std

    def seed(self):
        pass

    def __call__(self, tensor):
        """
        Args:
            tensor (Tensor): Tensor image of size (C, H, W) to be normalized.
        Returns:
            Tensor: Normalized Tensor image.
        """
        return normalize(tensor, self.mean, self.std)


class Resize(object):
    """Resize the input PIL Image to the given size.
    Args:
        size (sequence or int): Desired output size. If size is a sequence like
            (h, w), output size will be matched to this. If size is an int,
            smaller edge of the image will be matched to this number.
            i.e, if height > width, then image will be rescaled to
            (size * height / width, size)
        interpolation (int, optional): Desired interpolation. Default is
            ``PIL.Image.BILINEAR``
    """

    def __init__(self, size, interpolation=Image.BILINEAR):
        assert isinstance(size, int) or (isinstance(size, collections.Iterable) and len(size) == 2)
        self.size = size
        self.interpolation = interpolation

    def seed(self):
        pass

    def __call__(self, img):
        """
        Args:
            img (PIL Image): Image to be scaled.
        Returns:
            PIL Image: Rescaled image.
        """
        return resize(img, self.size, self.interpolation)


class Scale(Resize):
    """
    Note: This transform is deprecated in favor of Resize.
    """
    def __init__(self, *args, **kwargs):
        warnings.warn("The use of the transforms.Scale transform is deprecated, " +
                      "please use transforms.Resize instead.")
        super(Scale, self).__init__(*args, **kwargs)


class CenterCrop(object):
    """Crops the given PIL Image at the center.
    Args:
        size (sequence or int): Desired output size of the crop. If size is an
            int instead of sequence like (h, w), a square crop (size, size) is
            made.
    """

    def __init__(self, size):
        if isinstance(size, numbers.Number):
            self.size = (int(size), int(size))
        else:
            self.size = size

    @staticmethod
    def get_params(img, output_size):
        """Get parameters for ``crop`` for center crop.
        Args:
            img (PIL Image): Image to be cropped.
            output_size (tuple): Expected output size of the crop.
        Returns:
            tuple: params (i, j, h, w) to be passed to ``crop`` for center crop.
        """
        w, h = img.size
        th, tw = output_size
        i = int(round((h - th) / 2.))
        j = int(round((w - tw) / 2.))
        return i, j, th, tw

    def seed(self):
        pass

    def __call__(self, img):
        """
        Args:
            img (PIL Image): Image to be cropped.
        Returns:
            PIL Image: Cropped image.
        """
        i, j, h, w = self.get_params(img, self.size)
        return crop(img, i, j, h, w)


class Pad(object):
    """Pad the given PIL Image on all sides with the given "pad" value.
    Args:
        padding (int or tuple): Padding on each border. If a single int is provided this
            is used to pad all borders. If tuple of length 2 is provided this is the padding
            on left/right and top/bottom respectively. If a tuple of length 4 is provided
            this is the padding for the left, top, right and bottom borders
            respectively.
        fill: Pixel fill value. Default is 0. If a tuple of
            length 3, it is used to fill R, G, B channels respectively.
    """

    def __init__(self, padding, fill=0):
        assert isinstance(padding, (numbers.Number, tuple))
        assert isinstance(fill, (numbers.Number, str, tuple))
        if isinstance(padding, collections.Sequence) and len(padding) not in [2, 4]:
            raise ValueError("Padding must be an int or a 2, or 4 element tuple, not a " +
                             "{} element tuple".format(len(padding)))

        self.padding = padding
        self.fill = fill

    def seed(self):
        pass

    def __call__(self, img):
        """
        Args:
            img (PIL Image): Image to be padded.
        Returns:
            PIL Image: Padded image.
        """
        return pad(img, self.padding, self.fill)


class Lambda(object):
    """Apply a user-defined lambda as a transform.
    Args:
        lambd (function): Lambda/function to be used for transform.
    """

    def __init__(self, lambd):
        assert isinstance(lambd, types.LambdaType)
        self.lambd = lambd

    def seed(self):
        pass

    def __call__(self, img):
        return self.lambd(img)


class RandomHorizontalFlip(object):
    """Horizontally flip the given PIL Image randomly with a probability of 0.5."""

    def __init__(self):
        self.flip_flag = False

    def seed(self):
        if random.random() < 0.5:
            self.flip_flag = True

    def __call__(self, img):
        """
        Args:
            img (PIL Image): Image to be flipped.
        Returns:
            PIL Image: Randomly flipped image.
        """
        if self.flip_flag:
            return hflip(img)
        return img


class RandomVerticalFlip(object):
    """Vertically flip the given PIL Image randomly with a probability of 0.5."""
    def __init__(self):
        self.flip_flag = False

    def seed(self):
        if random.random() < 0.5:
            self.flip_flag = True

    def __call__(self, img):
        """
        Args:
            img (PIL Image): Image to be flipped.
        Returns:
            PIL Image: Randomly flipped image.
        """
        if self.flip_flag:
            return vflip(img)
        return img


class ColorJitter(object):
    """Randomly change the brightness, contrast and saturation of an image.
    Args:
        brightness (float): How much to jitter brightness. brightness_factor
            is chosen uniformly from [max(0, 1 - brightness), 1 + brightness].
        contrast (float): How much to jitter contrast. contrast_factor
            is chosen uniformly from [max(0, 1 - contrast), 1 + contrast].
        saturation (float): How much to jitter saturation. saturation_factor
            is chosen uniformly from [max(0, 1 - saturation), 1 + saturation].
        hue(float): How much to jitter hue. hue_factor is chosen uniformly from
            [-hue, hue]. Should be >=0 and <= 0.5.
    """
    def __init__(self, brightness=0, contrast=0, saturation=0, hue=0):
        self.brightness = brightness
        self.contrast = contrast
        self.saturation = saturation
        self.hue = hue
        self.transform = self.get_params(self.brightness, self.contrast,
                                    self.saturation, self.hue)

    def seed(self):
        self.transform = self.get_params(self.brightness, self.contrast,
                                    self.saturation, self.hue)

    @staticmethod
    def get_params(brightness, contrast, saturation, hue):
        """Get a randomized transform to be applied on image.
        Arguments are same as that of __init__.
        Returns:
            Transform which randomly adjusts brightness, contrast and
            saturation in a random order.
        """
        np.random.seed()
        transforms = []
        if brightness > 0:
            brightness_factor = np.random.uniform(max(0, 1 - brightness), 1 + brightness)
            transforms.append(Lambda(lambda img: adjust_brightness(img, brightness_factor)))

        if contrast > 0:
            contrast_factor = np.random.uniform(max(0, 1 - contrast), 1 + contrast)
            transforms.append(Lambda(lambda img: adjust_contrast(img, contrast_factor)))

        if saturation > 0:
            saturation_factor = np.random.uniform(max(0, 1 - saturation), 1 + saturation)
            transforms.append(Lambda(lambda img: adjust_saturation(img, saturation_factor)))

        if hue > 0:
            hue_factor = np.random.uniform(-hue, hue)
            transforms.append(Lambda(lambda img: adjust_hue(img, hue_factor)))

        np.random.shuffle(transforms)
        transform = Compose(transforms)

        return transform

    def __call__(self, img):
        """
        Args:
            img (PIL Image): Input image.
        Returns:
            PIL Image: Color jittered image.
        """
        return self.transform(img)

class Jitter(object):
    def __init__(self, x_pad=0.2, y_pad=0.2):
        self.x_pad = x_pad
        self.y_pad = y_pad
        self.l, self.r, self.t, self.b = self.get_params(self.x_pad, self.y_pad)

    def seed(self):
        self.l, self.r, self.t, self.b = self.get_params(self.x_pad, self.y_pad)

    @staticmethod
    def get_params(x_pad, y_pad):
        left   = random.random() * x_pad
        right  = random.random() * x_pad
        top    = random.random() * y_pad
        bottom = random.random() * y_pad

        return left, right, top, bottom

    def __call__(self, image):
        w, h = image.size

        left = math.floor(self.l * w)
        right = math.ceil(w - self.r * w)
        top = math.floor(self.t * h)
        bottom = math.ceil(h - self.b * h)

        image = image.crop(box=(left, top, right, bottom))

        return image

class Rotate(object):
    def __init__(self, angle=0.1):
        self.angle = angle
        self.rotation = self.get_params(self.angle)

    def seed(self):
        self.rotation = self.get_params(self.angle)

    @staticmethod
    def get_params(angle):
        return (random.random() - 0.5) * 2.0 * angle

    def __call__(self, image):
        np.random.seed()
        array = np.array(image)

        image = image.rotate(self.rotation)

        return image
'''
class Noise(object):
    def __init__(self, level=0.05):
        self.level = level

    def __call__(self, image):
        np.random.seed()
        array = np.float32(np.array(image))
        noise = np.random.randn(*array.shape).astype(np.float32)

        level = np.random.random() * self.level

        noise = noise / np.linalg.norm(noise) * np.linalg.norm(array) * level



        #print(np.linalg.norm(array), np.linalg.norm(noise))
        #print(array.shape, noise.shape)
        #print(array.sum(), noise.sum())
        #print(array.dtype, noise.dtype)
        array += noise
        #print(array.shape)

        array = array.clip(min=0.0, max=255.0)

        #print(array.max(), array.min())
        image = Image.fromarray(np.uint8(array))

        return image
'''
def get_box_area(left, upper, right, lower):
    return (right - left) * (lower - upper)

def generate_box(size):
    upper = np.random.randint(0, size)
    lower = np.random.randint(upper+1, size+1)
    left = np.random.randint(0, size)
    right = np.random.randint(left+1, size + 1)
    return (left, upper, right, lower)

def random_black_rectangle(img):
    box = generate_box(224)
    while(224**2 / 6 > get_box_area(*box) or get_box_area(*box) > 224**2 / 2):
        box = generate_box(224)
    region = img.crop(box)
    img.paste(Image.fromarray(
        np.random.randint(
            0, 255, size=np.array(region).shape).astype('uint8')), box)
    return img

class DummyDim(object):
    """add a dummy dimension
    """
    def __init__(self, dim=-1):
        self.dim = dim
    def __call__(self, tensor):
        """
        Args:
            tensor (Tensor): Tensor without dummy time
        Returns:
            tensor (Tensor): Tensor with dummy dim
        """

        return tensor.unsqueeze(self.dim)

#== MY TRANSFORMS START HERE

class Compose():
    def __init__(self, transforms):
        self.transforms = transforms

    def reset(self):
        for index in range(len(self.transforms)):
            self.transforms[index].reset()

    def __call__(self, tensor):
        result = tensor

        for index in range(len(self.transforms)):
            result = self.transforms[index](result)

        return result


class ToTensor():
    def __init__(self):
        pass

    def reset(self):
        pass

    def __call__(self, input):
        return torch.FloatTensor(input)


class RandomHFlip():
    def __init__(self, p=0.5):
        self.p = p
        self.flip = self.get_params(self.p)

    @staticmethod
    def get_params(p):
        return random.random() > p

    def reset(self):
        self.flip = self.get_params(self.p)

    def __call__(self, tensor):
        if self.flip:
            img = tensor.numpy()[:, :, ::-1]
        else:
            img = tensor.numpy()
        return torch.FloatTensor(numpy.array(img))


class RandomVFlip():
    def __init__(self, p=0.5):
        self.p = p
        self.flip = self.get_params(self.p)

    @staticmethod
    def get_params(p):
        return random.random() > p

    def reset(self):
        self.flip = self.get_params(self.p)

    def __call__(self, tensor):
        if self.flip:
            img = tensor.numpy()[:, ::-1, :]
        else:
            img = tensor.numpy()
        return torch.FloatTensor(numpy.array(img))


class Scale():
    def __init__(self, shape=[224, 224]):
        self.shape=shape

    def reset(self):
        pass

    def __call__(self, tensor):
        img = tensor.numpy().swapaxes(0, 1).swapaxes(1, 2)
        img_max = img.max()
        img_min = img.min()

        res = (img - img_min) / (img_max - img_min)

        res = skimage.transform.resize(res, self.shape,
                                       mode='reflect').swapaxes(1, 2).swapaxes(0, 1)

        res = res * (img_max - img_min) + img_min
        return torch.FloatTensor(res)

class CenterCrop():
    def __init__(self, size=[224, 224]):
        self.size = size
        
    def reset(self):
        pass
    
    def __call__(self, tensor):
        res = tensor.clone()
        
        for index in range(len(self.size)):
            start = int((tensor.shape[index + 1] - self.size[index]) * 0.5)
            res = res.transpose(index + 1, 0)[start:start + self.size[index]].transpose(0, index + 1)
        
        return res
    
class RandomCrop():
    def __init__(self, size=[224, 224]):
        self.size=size

        self.pad = self.get_params(self.size)


    @staticmethod
    def get_params(size):
        pad = []
        for index in range(len(size)):
            pad.append(int(random.random()))
        
        return pad


    def reset(self):
        self.pad = self.get_params(self.size)


    def __call__(self, tensor):
        res = tensor.clone()
        
        for index in range(len(self.size)):
            start = int((tensor.shape[index + 1] - self.size[index]) * self.pad[index])
            res = res.transpose(index + 1, 0)[start:start + self.size[index]].transpose(0, index + 1)
            
        return res


class RandomFixedCrop():
    def __init__(self, max_size=1.0, min_size=0.5):
        self.max_size = max_size
        self.min_size = min_size

        self.size, self.x_pad, self.y_pad = self.get_params(self.min_size, self.max_size)


    @staticmethod
    def get_params(min_size, max_size):
        size = random.random() * (min_size - max_size) + min_size
        pad_limit = 1.0 - size
        x_pad = random.random() * pad_limit
        y_pad = random.random() * pad_limit

        return size, x_pad, y_pad


    def reset(self):
        self.size, self.x_pad, self.y_pad = self.get_params(self.min_size, self.max_size)


    def __call__(self, tensor):
        x_start = int(self.x_pad * tensor.size(1))
        y_start = int(self.y_pad * tensor.size(2))

        x_size = int(self.size * tensor.size(1))
        y_size = int(self.size * tensor.size(2))

        return tensor[:, x_start:x_start+x_size, y_start:y_start+y_size]


class RandomJitter():
    def __init__(self, x_pad_limit=0.05, y_pad_limit=0.05):
        self.x_pad = x_pad_limit
        self.y_pad = y_pad_limit
        self.left, self.right, self.top, self.bottom = self.get_params(x_pad_limit, y_pad_limit)

    @staticmethod
    def get_params(x_pad, y_pad):
        left_pad = random.random() * x_pad
        right_pad = random.random() * x_pad
        top_pad = random.random() * y_pad
        bottom_pad = random.random() * y_pad

        return left_pad, right_pad, top_pad, bottom_pad


    def reset(self):
        self.left, self.right, self.top, self.bottom = self.get_params(x_pad_limit, y_pad_limit)


    def __call__(self, tensor):
        top_pad = int(tensor.size(1) * self.top)
        bottom_pad = tensor.size(1) - int(tensor.size(1) * self.bottom)
        left_pad = int(tensor.size(2) * self.left)
        right_pad = tensor.size(2) - int(tensor.size(2) * self.right)

        return tensor[:, top_pad:bottom_pad, left_pad:right_pad]


class RandomRotation(object):
    def __init__(self, angles=[-180.0, 180.0]):
        self.angles = angles

        self.angle = self.get_params(self.angles[0], self.angles[1])

    @staticmethod
    def get_params(min_angle, max_angle):
        angle = random.random() * (max_angle - min_angle) + min_angle
        return angle

    def reset(self):
        self.angle = self.get_params(self.angles[0], self.angles[1])

    def __call__(self, image):
        numpy.random.seed()
        res = image.numpy()

        image_max = res.max()
        image_min = res.min()

        res = (res - image_min) / (image_max - image_min)

        res = res.swapaxes(0, 1).swapaxes(1, 2)

        res = skimage.transform.rotate(res, self.angle)
        res = res.swapaxes(1, 2).swapaxes(0, 1)
        res = res * (image_max - image_min) + image_min
        res = torch.FloatTensor(res)

        return res

class RandomXYFlip:
    def __init__(self, p=0.5):
        self.p = 0.5
        self.flag = get_params(self.p)

    def reset(self):
        self.flag = get_params(self.p)

    @staticmethod
    def get_params(p):
        return random.random() > p

    def __call__(self, tensor):
        if self.flip:
            return tensor.transpose(1, 2)
        return tensor
    

class Normalize(object):
    def __init__(self, mean, std):
        self.mean = mean
        self.std = std

    def reset(self):
        pass

    def __call__(self, tensor):
        return normalize(tensor, self.mean, self.std)
#def g_noise():
#    pass

#def p_noise():
#    pass

#def rot():
#    pass