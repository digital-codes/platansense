import os
import cairo
import freetype
import sys
import math

A4_WIDTH = 595
A4_HEIGHT = 842
MM_TO_PT = 2.83465

# generaate qrcodes like so:
# for i in 1 2 3 4 5 6 7 8 9 10 11 12; do qrencode -s 7 -m 10 -d 150 "https://ok-lab-karlsruhe.de/projects/platane/sensor/qr_$i" -o qr_$i.png; done 


# Function to set font using FreeType
def set_font(context, font_path, font_size):
    try:
        face = freetype.Face(font_path)
        faceName = face.family_name.decode("utf-8")
        face.set_char_size(font_size * 64)
        context.set_font_face(cairo.ToyFontFace(faceName))
        context.set_font_size(font_size)
        #print(f"Loaded font: {font_path} at size {font_size}")
    except Exception as e:
        print(f"Error setting font: {e}")


# Function to set color
def set_color(context, color):
    normalized_color = [c / 255.0 for c in color]
    context.set_source_rgb(*normalized_color)
    #print(f"Set color: {normalized_color}")


# Function to draw text at a position
def draw_text(context, text, x, y, scale_x=100, scale_y=100, rotate=0):
    context.save()
    context.translate(x, y)
    if scale_x != 100 or scale_y != 100:
        #print(f"Scaling text by {scale_x}% x {scale_y}%")
        context.move_to(0, 0)
        context.scale(scale_x / 100, scale_y / 100)
    context.rotate((rotate + 90) * math.pi / 180)
    context.show_text(text)
    context.stroke()
    context.restore()


# Function to draw an image with resizing
def draw_image(context, image_path, x, y, width, height, rotate=0):
    print(f"Loading image: {image_path}")
    image_surface = cairo.ImageSurface.create_from_png(image_path)
    img_width = image_surface.get_width()
    img_height = image_surface.get_height()
    # scale = width / img_width
    scale = height / img_height

    context.save()
    # Move to the center of the target area
    context.translate(x + width / 2, y + height / 2)
    # Rotate
    context.rotate(rotate * math.pi / 180)
    # Scale to fit the desired width and height
    context.scale(width / img_width, height / img_height)
    # Move the image so its center is at the origin
    context.translate(-img_width / 2, -img_height / 2)
    context.set_source_surface(image_surface, 0, 0)
    context.get_source().set_filter(cairo.FILTER_NEAREST)
    context.paint()
    context.restore()


# Main function
def main(args):

    output_file = "qrcircle.pdf"
    # print("Layout data:", layout_data)
    font = "Cabin-Regular.ttf"
    fontpath = "/home/kugel/.local/share/fonts"
    fontSize = 16

    color = [0,0,0]

    files = os.listdir(".")
    qrs = [f for f in files if f.startswith("qr_") and f.endswith(".png")]  
    circleWidth = 180 * MM_TO_PT
    imageSize = 30 * MM_TO_PT

    # Center of the page
    center_x = A4_WIDTH / 2
    center_y = A4_HEIGHT / 2

    # Radius for placing QR codes (adjust as needed)
    radius = (circleWidth - imageSize) / 2
    textRadius = radius - imageSize * .6

    # Compute x, y offsets for 12 positions (every 30°)
    positions = []
    textPositions = []
    for i in range(12):
        angle_deg = i * 30
        angle_rad = math.radians(angle_deg)
        x = center_x + radius * math.cos(angle_rad)
        y = center_y + radius * math.sin(angle_rad)
        positions.append((x, y))
        x = center_x + textRadius * math.cos(angle_rad)
        y = center_y + textRadius * math.sin(angle_rad)
        textPositions.append((x, y))
    print("QR code positions:", positions)
    #print("Text positions:", textPositions)

    surface = cairo.PDFSurface(output_file, A4_WIDTH, A4_HEIGHT)  # A4 size
    context = cairo.Context(surface)

    set_color(context, color)
    set_font(context, os.sep.join([fontpath, font]), fontSize)

    # center circle
    context.set_line_width(1)
    context.arc(center_x, center_y, 5 * MM_TO_PT / 2, 0, 2 * 3.1416)
    context.stroke()    
    

    for image in qrs:
        image_path = os.path.join(".", image)
        index = int(image.split("_")[1].split(".")[0]) - 1
        x, y = positions[index]
        print(f"Drawing QR code {image} at position {index + 1}: ({x}, {y})")
        draw_image(context, image_path, x - imageSize / 2, y - imageSize / 2, imageSize, imageSize, rotate=index * 30)


        draw_text(
            context,
            f"{str(index + 1).ljust(2)}",
            x=textPositions[index][0],
            y=textPositions[index][1],
            scale_x=100, scale_y=100,
            rotate=(index * 30)
        )


    # Finish PDF
    context.show_page()
    surface.finish()
    print("PDF generated successfully.")


if __name__ == "__main__":
    main(sys.argv)
