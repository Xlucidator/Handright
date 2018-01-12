""" The core module """
import math
import multiprocessing
import random

import PIL.Image
import PIL.ImageDraw

_MAX_BYTE_VALUE = 255

# Chinese, English and other end chars
_DEFAULT_END_CHARS = "，。》、？；：’”】｝、！％）" + ",.>?;:]}!%)" + "′″℃℉"


def handwrite(text, template: dict, worker: int = 0) -> list:
    """
    Simulating Chinese handwriting through introducing numerous randomness in the process.
    The module uses a Cartesian pixel coordinate system, with (0,0) in the upper left corner as same as Pillow Module.
    Note that, the module is built for simulating Chinese handwriting instead of English (or other languages')
    handwriting. Though injecting pieces of exotic language generally may not effect the overall performance, you should
    NOT count on it has a great performance in the domain of non-Chinese handwriting.

    :param text: <Iterable>
        a char Iterable

    :param template: a dict containing the settings of the template
        The dict should contain below settings:
        'background': <Image> (from PIL.Image)
        'box': (<int>, <int>, <int>, <int>)
            A bounding box as a 4-tuple defining the left, upper, right, and lower pixel coordinate
            NOTE: The bounding area should be in the 'background'. In other words, it should be in (0, 0,
            background.width, background.height).
            NOTE: The function do NOT guarantee the drawn texts will completely in the 'box' due to the used randomness.
        'font': <Font> (from PIL.ImageFont)
            NOTE: the size attribute of the font object means nothing in the function.
        'font_size': <int>
            The average font size in pixel
            NOTE: (box[3] - box[1]) must be greater than font_size.
            NOTE: (box[2] - box[0]) must be greater than font_size.
        'color': (<int>, <int>, <int>)
            The color of font in RGB. These values must be between 0 (inclusive) and 255 (inclusive).
            default: (0, 0, 0)
        'word_spacing': <int>
            The average gap between two adjacent chars in pixel
            default: 0
        'line_spacing': <int>
            The average gap between two adjacent lines in pixel
            default: font_size // 5

        Advanced:
        'font_size_sigma': <float>
            The sigma of the gauss distribution of the font size
            default: font_size / 256
        'line_spacing_sigma': <float>
            The sigma of the gauss distribution of the line spacing
            default: font_size / 256
        'word_spacing_sigma': <float>
            The sigma of the gauss distribution of the word spacing
            default: font_size / 256
        'is_half_char': <Callable>
            A function judges whether or not a char only take up half of its original width
            The function must take a char parameter and return a boolean value.
            The feature is designed for some of Chinese punctuations that only take up the left half of their
            space (e.g. '，', '。').
            default: (lambda c: False)
        'is_end_char': <Callable>
            A function judges whether or not a char can NOT be in the beginning of the lines (e.g. '，' , '。', '》')
            The function must take a char parameter and return a boolean value.
            default: (lambda c: c in _DEFAULT_END_CHARS)
        'alpha_x': <float>
            A float that controls the degree of the distortion in the horizontal direction
            its value must be between 0(inclusive) and 1(inclusive).
            default: 0.1
        'alpha_y': <float>
            A float that controls the degree of the distortion in the vertical direction
            its value must be between 0(inclusive) and 1(inclusive).
            default: 0.1

    :param worker: <int>
        the number of worker
        if worker is less than or equal to 0, the actual amount of worker would be multiprocessing.cpu_count() + worker.
        default: 0 (use all the available CPU in the computer)

    :return: <list<Image>>
        a list of drawn images with RGB mode and the same size as the background
    """
    template = dict(template)
    font_size = template['font_size']

    if 'color' not in template:
        template['color'] = (0, 0, 0)
    if 'word_spacing' not in template:
        template['word_spacing'] = 0
    if 'line_spacing' not in template:
        template['line_spacing'] = font_size // 5

    if 'font_size_sigma' not in template:
        template['font_size_sigma'] = font_size / 256
    if 'line_spacing_sigma' not in template:
        template['line_spacing_sigma'] = font_size / 256
    if 'word_spacing_sigma' not in template:
        template['word_spacing_sigma'] = font_size / 256

    if 'is_half_char' not in template:
        template['is_half_char'] = lambda c: False
    if 'is_end_char' not in template:
        template['is_end_char'] = lambda c: c in _DEFAULT_END_CHARS

    if 'alpha_x' not in template:
        template['alpha_x'] = 0.1
    if 'alpha_y' not in template:
        template['alpha_y'] = 0.1

    worker = worker if worker > 0 else multiprocessing.cpu_count() + worker
    return _handwrite(text, template, worker)


def _handwrite(text, template: dict, worker: int) -> list:
    images = _draw_text(text, size=template['background'].size, **template)
    if not images:
        return images
    render = _RenderMaker(**template)
    with multiprocessing.Pool(min(worker, len(images))) as pool:
        images = pool.map(render, images)
    return images


def _draw_text(
        text,
        size: tuple,
        box: tuple,
        font,
        font_size: int,
        color: tuple,
        font_size_sigma: float,
        line_spacing: int,
        line_spacing_sigma: float,
        word_spacing: int,
        word_spacing_sigma: float,
        is_end_char,
        is_half_char,
        **kwargs
) -> list:
    """
    Draw the text randomly in blank images
    :return: a list of drawn images with RGB mode and given size
    NOTE: (box[3] - box[1]) must be greater than font_size.
    NOTE: (box[2] - box[0]) must be greater than font_size.
    """
    if not box[3] - box[1] > font_size:
        raise ValueError("(box[3] - box[1]) must be greater than font_size.")
    if not box[2] - box[0] > font_size:
        raise ValueError("(box[2] - box[0]) must be greater than font_size.")

    left, upper, right, lower = box
    chars = iter(text)
    images = []
    try:
        char = next(chars)
        while True:
            image = PIL.Image.new('RGB', size, color=(_MAX_BYTE_VALUE, _MAX_BYTE_VALUE, _MAX_BYTE_VALUE))
            draw = PIL.ImageDraw.Draw(image)
            y = upper
            try:
                while y < lower - font_size:
                    x = left
                    while True:
                        if char == '\n':
                            char = next(chars)
                            break
                        if x >= right - font_size and not is_end_char(char):
                            break
                        actual_font_size = max(int(random.gauss(font_size, font_size_sigma)), 0)
                        xy = (x, int(random.gauss(y, line_spacing_sigma)))
                        font = font.font_variant(size=actual_font_size)
                        draw.text(xy, char, fill=color, font=font)
                        font_width = font.getsize(char)[0]
                        x_step = word_spacing + font_width * (1 / 2 if is_half_char(char) else 1)
                        x += int(random.gauss(x_step, word_spacing_sigma))
                        char = next(chars)
                    y += line_spacing + font_size
                images.append(image)
            except StopIteration:
                images.append(image)
                raise StopIteration()
    except StopIteration:
        return images


class _RenderMaker:
    """
    The maker of the function-like object rendering the foreground that was drawn text and returning finished image
    """

    def __init__(
            self,
            background,
            color: tuple,
            font_size: int,
            alpha_x: float,
            alpha_y: float,
            **kwargs
    ):
        self.__background = background
        self.__color = color
        self.__font_size = font_size
        self.__alpha_x = alpha_x
        self.__alpha_y = alpha_y
        self.__random = random.Random()

    def __call__(self, image):
        self.__random.seed()
        self.__perturb(image)
        return self.__merge(image)

    def __perturb(self, image) -> None:
        """
        'perturb' the image and generally make the glyphs from same chars, if any, seem different
        NOTE: self.__alpha_x must be between 0 (inclusive) and 1 (inclusive).
        NOTE: self.__alpha_y must be between 0 (inclusive) and 1 (inclusive).
        """
        if not 0 <= self.__alpha_x <= 1:
            raise ValueError("alpha_x must be between 0 (inclusive) and 1 (inclusive).")
        if not 0 <= self.__alpha_y <= 1:
            raise ValueError("alpha_y must be between 0 (inclusive) and 1 (inclusive).")

        wavelength = 2 * self.__font_size
        matrix = image.load()
        for i in range((image.width + wavelength) // wavelength + 1):
            x0 = self.__random.randrange(-wavelength, image.width)
            for j in range(max(0, -x0), min(wavelength, image.width - x0)):
                offset = self.__alpha_x * wavelength / (2 * math.pi) * (1 - math.cos(2 * math.pi * j / wavelength))
                self.__slide_x(matrix, x0 + j, offset, image.height)
        for i in range((image.height + wavelength) // wavelength + 1):
            y0 = self.__random.randrange(-wavelength, image.height)
            for j in range(max(0, -y0), min(wavelength, image.height - y0)):
                offset = self.__alpha_y * wavelength / (2 * math.pi) * (1 - math.cos(2 * math.pi * j / wavelength))
                self.__slide_y(matrix, y0 + j, offset, image.width)

    @staticmethod
    def __slide_x(matrix, x: int, offset: float, height: int) -> None:
        """
        The helper function of __perturb()
        Slide one given column without producing jaggies
        :param offset: a float value greater than or equal to 0
        """
        weight = offset % 1
        for i in range(height - math.ceil(offset)):
            matrix[x, i] = (
                int((1 - weight) * matrix[x, i + math.floor(offset)][0] + weight * matrix[x, i + math.ceil(offset)][0]),
                int((1 - weight) * matrix[x, i + math.floor(offset)][1] + weight * matrix[x, i + math.ceil(offset)][1]),
                int((1 - weight) * matrix[x, i + math.floor(offset)][2] + weight * matrix[x, i + math.ceil(offset)][2])
            )
        for i in range(height - math.ceil(offset), height):
            matrix[x, i] = (_MAX_BYTE_VALUE, _MAX_BYTE_VALUE, _MAX_BYTE_VALUE)

    @staticmethod
    def __slide_y(matrix, y: int, offset: float, width: int) -> None:
        """
        The helper function of __perturb()
        Slide one given row without producing jaggies
        :param offset: a float value greater than or equal to 0
        """
        weight = offset % 1
        for i in range(width - math.ceil(offset)):
            matrix[i, y] = (
                int((1 - weight) * matrix[i + math.floor(offset), y][0] + weight * matrix[i + math.ceil(offset), y][0]),
                int((1 - weight) * matrix[i + math.floor(offset), y][1] + weight * matrix[i + math.ceil(offset), y][1]),
                int((1 - weight) * matrix[i + math.floor(offset), y][2] + weight * matrix[i + math.ceil(offset), y][2]),
            )
        for i in range(width - math.ceil(offset), width):
            matrix[i, y] = (_MAX_BYTE_VALUE, _MAX_BYTE_VALUE, _MAX_BYTE_VALUE)

    def __merge(self, image):
        """ Merge the foreground and the background image """
        image.paste(self.__background, mask=image.convert(mode='L'))
        return image