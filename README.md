# PystegImage

**PystegImage** is a application that allows you to hide messages in images (Steganography)

# Prerequisites

To use the program, you need:
1. Python
2. Pillow
3. customtkinter
4. Visual Studio

------------------------------------------------------------------------

# Setup
Create a virtual environment in the root of the project

Then install customtkinter and pillow

------------------------------------------------------------------------
# To run

If using visual studio, you can run the program by first running the python Frontend program

From there a GUI will show you how to use the program.

-------------------------------------------------------------------------
# Navigation

ENCODING
1. Cover Image (The image the message will be encoded into)
2. Secret message (The text that will be encoded, can either be typed directly or a text file)
3. Where the encoded image is saved

DECODING
1. Encoded Image (The image with the message in it)
2. Decoded Message Save Location (where the text file with the message is saved).

---------------------------------------------------------------------------
# Final Notes
A update will add cryptography to allow a message to be encoded itself. The LSB method is quite popular.

Claude did help create the frontend and touch up the backend to fix some bugs.
