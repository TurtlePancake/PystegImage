#Image based steganography using LSB method, Creates and Decodes them
from pathlib import Path

from PIL import Image


#Each message byte is stored across 9 colour values: 8 hold the bits and the
#9th is a "keep going" flag 
VALUES_PER_BYTE = 9


class PyStegEncoder():
    def __init__(self, imagePath, messageSource, messageText, messageFilePath, outputImagePath):

        #Sets up values when created
        self.imagePath = imagePath

        self.messageSource = messageSource

        self.messageText = messageText

        self.messageFilePath = messageFilePath

        self.outputImagePath = outputImagePath


        


    #Returns the message to hide. If a text file selected, read from the file
    def getMessage(self):
        if self.messageSource == "file":
            if not self.messageFilePath:
                raise ValueError("No message file was selected.")
            return Path(self.messageFilePath).read_text(encoding='utf-8')

        return self.messageText or ""



    #Checks the image size of the image to see if message can be encoded
    def checkImageSize(self):
        image = Image.open(self.imagePath)
        width, height = image.size
        maxCapacity = width * height * 3 // VALUES_PER_BYTE

        if len(self.convertToBinary(self.getMessage())) > maxCapacity:
            return False
        else:
            return True



    #converts text to binary, a list of 8 bit strings
    def convertToBinary(self, text):
        #UTF-8 first: format(ord(char), '08b') gives more than 8 bits for any
        #non-ASCII character, which throws the whole bitstream out of step.
        binaryText = [format(byte, '08b') for byte in text.encode('utf-8')]



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
        for pixel in self.modifyPixel(originalPixels, self.getMessage()):
            newImage.putpixel((a % newImage.size[0], a // newImage.size[0]), pixel)
            a += 1


        #Saves the new image with the encoded message to the output path. Cannot be JPG
        newImage.save(self.outputImagePath)



        




class PyStegDecoder():
    def __init__(self, imagePath, outputMessagePath):

        self.imagePath = imagePath
        self.outputMessagePath = outputMessagePath



    #converts text to binary, a list of 8 bit strings
    def convertToBinary(self, text):
        binaryText = [format(byte, '08b') for byte in text.encode('utf-8')]
        return binaryText

    #Converts binary to text
    def convertToText(self, binaryString):

        #The encoder writes UTF-8 bytes, so the bits are rebuilt into bytes and
        #decoded in one go - a character can span several of them.
        messageBytes = bytearray()
        for i in range(0, len(binaryString), 8):
            byte = binaryString[i:i + 8]
            messageBytes.append(int(byte, 2))
        return messageBytes.decode('utf-8', errors='replace')

    def decode(self):
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

        decodedMessage = self.convertToText(decodedMessage)

        return decodedMessage













