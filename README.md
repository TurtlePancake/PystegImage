# PystegImage

**PystegImage** is a application that allows you to hide messages in images (Steganography)

Messages are encrypted before they are hidden. A password is turned into an
encryption key with Argon2id, the message is encrypted with Fernet
(AES-128-CBC + HMAC), and the random salt travels inside the image, so the
recipient only needs the image and the password.

# Prerequisites

To use the program, you need:
1. Python
2. Pillow
3. customtkinter
4. argon2-cffi
5. cryptography
6. Visual Studio

------------------------------------------------------------------------

# Setup
Create a virtual environment in the root of the project

Then install the dependencies

```
pip install customtkinter pillow argon2-cffi cryptography
```

------------------------------------------------------------------------
# To run

If using visual studio, you can run the program by first running the python Frontend program

From there a GUI will show you how to use the program.

-------------------------------------------------------------------------
# Navigation

ENCODING
1. Cover Image (The image the message will be encoded into)
2. Secret message (The text that will be encoded, can either be typed directly or a text file)
3. Encryption (Type a password, press Generate, or leave the box empty to have one
   generated for you. Once encoding finishes the password is shown in a window with a
   copy button - save it, because it is the only way to read the message back.
   Switching to "No encryption" hides the message as plain text like the old version did)
4. Where the encoded image is saved

DECODING
1. Encoded Image (The image with the message in it)
2. Password (the one the sender gave you, leave empty for an image encoded without encryption)
3. Decoded Message Save Location (where the text file with the message is saved).

---------------------------------------------------------------------------
# How the encryption works

1. Argon2id turns the password plus a random 16 byte salt into a 32 byte key.
2. Fernet encrypts the message with that key.
3. The salt, the Argon2 settings and the ciphertext are packed into one block of
   bytes and that block is what gets hidden in the pixels.
4. Decoding reads the block back out, rebuilds the key from the stored salt and
   the password you type, and decrypts. A wrong password fails Fernet's built in
   HMAC check, so you get a clear "Incorrect password" message instead of garbled text.

Images made by the older plain text version still decode - the program tells the
two apart by a marker at the start of the hidden data.

---------------------------------------------------------------------------
# Final Notes
The LSB method is quite popular.

Claude did help create the frontend and touch up the backend to fix some bugs.
