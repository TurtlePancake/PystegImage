#Image based steganography using LSB method, Creates and Decodes them
#Messages can also be encrypted first: Argon2id turns a password into a key,
#Fernet (AES-128-CBC + HMAC) encrypts the message with it, and the salt travels
#inside the image so only the password is needed to read it back.
import base64
import os
import secrets
import struct
from pathlib import Path

from PIL import Image

from argon2.low_level import Type, hash_secret_raw
from cryptography.fernet import Fernet, InvalidToken


#Each message byte is stored across 9 colour values: 8 hold the bits and the
#9th is a stop or go flag.
VALUES_PER_BYTE = 9


#---------------------------------------------------------------------------
#Encryption layer
#---------------------------------------------------------------------------

#Argon2id settings. They are written into the payload header so an image made
#with today's settings still decodes if these defaults are raised later.
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536      #in KiB, so 64 MiB
ARGON2_PARALLELISM = 4

SALT_BYTES = 16
KEY_BYTES = 32                  #Fernet wants a 32 byte key, base64 encoded

#Alphabet for generated passwords. I, l, O, 0 and 1 are left out so a password
#can be read out loud or copied by hand without confusion.
PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"

#Binary payload layout (everything big endian, no padding):
#
#  magic        4 bytes   b'PSTG', marks the payload as encrypted
#  version      1 byte    payload format version
#  time cost    4 bytes   Argon2 iterations
#  memory cost  4 bytes   Argon2 memory in KiB
#  parallelism  1 byte    Argon2 lanes
#  salt length  1 byte    length of the salt that follows
#  cipher len   4 bytes   length of the ciphertext that follows
#  salt         <salt length> bytes
#  ciphertext   <cipher len> bytes   the raw bytes of the Fernet token
#
#The Fernet token is base64 text, so it is decoded back to its raw bytes before
#being packed. That saves a third of the image space and is put back exactly as
#it was on the way out. Everything after the header is opaque to the
#steganography layer, which just carries bytes.
PAYLOAD_MAGIC = b'PSTG'
PAYLOAD_VERSION = 1
HEADER_FORMAT = '>4sBIIBBI'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)


class StegCryptoError(Exception):
    """Base class for anything that goes wrong in the encryption layer."""


class PasswordRequiredError(StegCryptoError):
    """The image holds an encrypted message but no password was supplied."""


class WrongPasswordError(StegCryptoError):
    """The password did not decrypt the message."""


class PayloadFormatError(StegCryptoError):
    """The encrypted payload is damaged or was made by another version."""


#Builds a strong random password, in dash separated groups so it is readable
def generatePassword(groups=5, groupSize=5):
    chunks = [
        ''.join(secrets.choice(PASSWORD_ALPHABET) for _ in range(groupSize))
        for _ in range(groups)
    ]
    return '-'.join(chunks)


#Turns a password and salt into a Fernet key using Argon2id
def deriveKey(password, salt, timeCost=ARGON2_TIME_COST,
              memoryCost=ARGON2_MEMORY_COST, parallelism=ARGON2_PARALLELISM):
    if not password:
        raise ValueError("A password is needed to derive the encryption key.")

    rawKey = hash_secret_raw(
        secret=password.encode('utf-8'),
        salt=salt,
        time_cost=timeCost,
        memory_cost=memoryCost,
        parallelism=parallelism,
        hash_len=KEY_BYTES,
        type=Type.ID,
    )

    #Fernet keys are 32 raw bytes in urlsafe base64
    return base64.urlsafe_b64encode(rawKey)


#Packs the header, salt and ciphertext into one block of bytes
def packPayload(salt, token, timeCost=ARGON2_TIME_COST,
                memoryCost=ARGON2_MEMORY_COST, parallelism=ARGON2_PARALLELISM):
    cipherBytes = base64.urlsafe_b64decode(token)

    header = struct.pack(
        HEADER_FORMAT, PAYLOAD_MAGIC, PAYLOAD_VERSION,
        timeCost, memoryCost, parallelism, len(salt), len(cipherBytes),
    )

    return header + salt + cipherBytes


#True if these bytes look like one of our encrypted payloads. Checking the
#version as well as the magic keeps a plain message that happens to start with
#"PSTG" from being mistaken for an encrypted one.
def isEncryptedPayload(payload):
    if len(payload) < HEADER_SIZE:
        return False

    return payload[:4] == PAYLOAD_MAGIC and payload[4] == PAYLOAD_VERSION


#Splits a payload back into its Argon2 settings, salt and Fernet token
def unpackPayload(payload):
    if not isEncryptedPayload(payload):
        raise PayloadFormatError("The hidden data is not an encrypted PystegImage payload.")

    (magic, version, timeCost, memoryCost,
     parallelism, saltLen, cipherLen) = struct.unpack(HEADER_FORMAT, payload[:HEADER_SIZE])

    body = payload[HEADER_SIZE:]

    if len(body) < saltLen + cipherLen:
        raise PayloadFormatError(
            "The encrypted payload is incomplete - the image may have been "
            "resaved, resized or re-compressed after encoding."
        )

    salt = body[:saltLen]
    cipherBytes = body[saltLen:saltLen + cipherLen]

    return {
        "version": version,
        "timeCost": timeCost,
        "memoryCost": memoryCost,
        "parallelism": parallelism,
        "salt": salt,
        "token": base64.urlsafe_b64encode(cipherBytes),
    }


#Encrypts a message and returns (payload bytes, password). If no password is
#given a strong one is generated, which is why the password comes back out -
#the caller has to show it to the user.
def encryptMessage(messageText, password=None):
    if not password:
        password = generatePassword()

    salt = os.urandom(SALT_BYTES)
    key = deriveKey(salt=salt, password=password)
    token = Fernet(key).encrypt(messageText.encode('utf-8'))

    return packPayload(salt, token), password


#Reverses encryptMessage: rebuilds the key from the payload's salt and the
#supplied password, then decrypts
def decryptPayload(payload, password):
    if not password:
        raise PasswordRequiredError("This image holds an encrypted message, so a password is needed.")

    details = unpackPayload(payload)

    key = deriveKey(
        password=password,
        salt=details["salt"],
        timeCost=details["timeCost"],
        memoryCost=details["memoryCost"],
        parallelism=details["parallelism"],
    )

    #Fernet checks its own HMAC, so a wrong password shows up as InvalidToken
    #rather than as garbled text
    try:
        plainBytes = Fernet(key).decrypt(details["token"])
    except InvalidToken:
        raise WrongPasswordError(
            "Wrong password, or the hidden message has been altered."
        ) from None

    try:
        return plainBytes.decode('utf-8')
    except UnicodeDecodeError:
        raise PayloadFormatError("The message decrypted but is not valid text.") from None


class PyStegEncoder():
    def __init__(self, imagePath, messageSource, messageText, messageFilePath, outputImagePath,
                 encrypt=False, password=None):

        #Sets up values when created
        self.imagePath = imagePath

        self.messageSource = messageSource

        self.messageText = messageText

        self.messageFilePath = messageFilePath

        self.outputImagePath = outputImagePath

        #When encrypt is on and no password is given, one is generated during
        #encoding and left in self.password for the caller to show the user
        self.encrypt = encrypt

        self.password = password

        #The payload is built once and kept, so the size check and the encode
        #run against the same bytes and Argon2 is only ever run once
        self._payload = None


    #Returns the message to hide. If a text file selected, read from the file
    def getMessage(self):
        if self.messageSource == "file":
            if not self.messageFilePath:
                raise ValueError("No message file was selected.")
            return Path(self.messageFilePath).read_text(encoding='utf-8')

        return self.messageText or ""



    #Returns the bytes that actually go into the image: the plain message as
    #UTF-8, or the encrypted payload (header + salt + ciphertext)
    def getPayload(self):
        if self._payload is None:
            message = self.getMessage()

            if self.encrypt:
                self._payload, self.password = encryptMessage(message, self.password)
            else:
                self._payload = message.encode('utf-8')

        return self._payload



    #Checks the image size of the image to see if message can be encoded
    def checkImageSize(self):
        image = Image.open(self.imagePath)
        width, height = image.size
        maxCapacity = width * height * 3 // VALUES_PER_BYTE

        if len(self.getPayload()) > maxCapacity:
            return False
        else:
            return True



    #converts the message to binary, a list of 8 bit strings
    def convertToBinary(self, message):
        #UTF-8 first: format(ord(char), '08b') gives more than 8 bits for any
        #non-ASCII character, which throws the whole bitstream out of step.
        #Encrypted payloads arrive as bytes already and are used as they are.
        messageBytes = message.encode('utf-8') if isinstance(message, str) else message

        binaryText = [format(byte, '08b') for byte in messageBytes]



        return binaryText

    def modifyPixel(self, pixel, message):
        #modifys the pixel data
        messageDataList = self.convertToBinary(message)
        messageDataLen = len(messageDataList)
        imageData = iter(pixel)

        #follows the LSB Method here we go!
        for x in range(messageDataLen):
            pixels = [v for v in next(imageData)[:3] + next(imageData)[:3] + next(imageData)[:3]]

            #8 bits
            for i in range(8):
                #if the bit is 1, make the pixel value odd, if 0 make it even
                if messageDataList[x][i] == '0' and pixels[i] % 2 != 0:
                    pixels[i] -= 1
                elif messageDataList[x][i] == '1' and pixels[i] % 2 == 0:
                    if pixels[i] != 0:
                        pixels[i] -= 1
                    else:
                        pixels[i] += 1

            #Next is to check if the message is done, if it is, we make the 9th
            #value odd as a stop marker. 
            if x == messageDataLen - 1:
                if pixels[8] % 2 == 0:
                    if pixels[8] != 0:
                        pixels[8] -= 1
                    else:
                        pixels[8] += 1
            elif pixels[8] % 2 != 0:
                pixels[8] -= 1

            #Done three times since RGB values are three, we yield the modified pixel values
            yield tuple(pixels[:3])
            yield tuple(pixels[3:6])
            yield tuple(pixels[6:9])

    def encode(self):
        #Opens the image in read mode

        image = Image.open(self.imagePath, 'r')


        #Creates a copy of the image that will be the new image.
        newImage = image.convert("RGB")


        #encodes the message into the image using the modifyPixel function
        originalPixels = list(newImage.getdata())

        a = 0

        #Puts the modified pixel values into the new image, one pixel at a time
        for pixel in self.modifyPixel(originalPixels, self.getPayload()):
            newImage.putpixel((a % newImage.size[0], a // newImage.size[0]), pixel)
            a += 1


        #Saves the new image with the encoded message to the output path. Cannot be JPG
        newImage.save(self.outputImagePath)

        #Handing the password back means the frontend can show it without having
        #to know whether it was typed in or generated here
        return self.password if self.encrypt else None



        




class PyStegDecoder():
    def __init__(self, imagePath, outputMessagePath, password=None):

        self.imagePath = imagePath
        self.outputMessagePath = outputMessagePath

        #Only needed if the image turns out to hold an encrypted payload
        self.password = password



    #converts text to binary, a list of 8 bit strings
    def convertToBinary(self, text):
        binaryText = [format(byte, '08b') for byte in text.encode('utf-8')]
        return binaryText

    #Converts a bit string back into the raw bytes that were hidden
    def convertToBytes(self, binaryString):
        messageBytes = bytearray()
        for i in range(0, len(binaryString), 8):
            byte = binaryString[i:i + 8]
            messageBytes.append(int(byte, 2))
        return bytes(messageBytes)

    #Converts binary to text
    def convertToText(self, binaryString):

        #The encoder writes UTF-8 bytes, so the bits are rebuilt into bytes and
        #decoded in one go - a character can span several of them.
        return self.convertToBytes(binaryString).decode('utf-8', errors='replace')

    #True if the image holds an encrypted payload, so the frontend can ask for a
    #password before trying to decode
    def isEncrypted(self):
        return isEncryptedPayload(self.decodeBytes())

    def decodeBytes(self):
        #Opens the image in read mode
        image = Image.open(self.imagePath, 'r')

        #Same conversion as the encoder so palette and RGBA images decode too
        imgData = iter(image.convert("RGB").getdata())

        decodedMessage =""

        while True:
            #An image with no message in it has no stop marker, so we can run
            #out of pixels.
            try:
                pixels = [v for v in next(imgData)[:3] + next(imgData)[:3] + next(imgData)[:3]]
            except StopIteration:
                raise ValueError(
                    "No hidden message found - reached the end of the image "
                    "without finding the end-of-message marker."
                ) from None

            #Extracts the LSB from each pixel value and adds it to the decoded message
            for i in range(0, 8):
                if pixels[i] % 2 == 0:
                    decodedMessage += '0'
                else:
                    decodedMessage += '1'

            #Checks if the stop byte has been reached, if it has, we break out of the loop
            if pixels[8] % 2 != 0:
                break

        return self.convertToBytes(decodedMessage)

    def decode(self):
        payload = self.decodeBytes()

        #An encrypted payload is recognised by its header, so plain images made
        #before encryption existed still decode the old way
        if isEncryptedPayload(payload):
            return decryptPayload(payload, self.password)

        return payload.decode('utf-8', errors='replace')













