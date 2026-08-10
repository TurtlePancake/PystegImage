#Image based steganography using LSB method, Creates and Decodes them
from PIL import Image


class PyStegEncoder():
    def __init__(self, imagePath, messageSource, messageText, messageFilePath, outputImagePath):

        #Sets up values when created
        self.imagePath = imagePath

        self.messageSource = messageSource

        self.messageText = messageText

        self.messageFilePath = messageFilePath

        self.outputImagePath = outputImagePath


        


    #Checks the image size of the image to see if message can be encoded
    def checkImageSize(self):
        image = Image.open(self.imagePath)
        width, height = image.size
        maxCapacity = width * height * 3 // 8

        if len(self.messageText) > maxCapacity:
            return False
        else:
            return True



    #converts text to binary, a list of 8 bit strings
    def convertToBinary(self, text):
        binaryText = [format(ord(char), '08b') for char in text]

        

        return binaryText

    def modifyPixel(self, pixel, message):
        #modifys the pixel data
        messageDataList = self.convertToBinary(message)
        messageDataLen = len(messageDataList)
        imageData = iter(pixel)

        #follows the LSB Method here we go!
        for x in range(messageDataLen):
            pixels = [v for v in next(imageData)[:3] + next(imageData)[:3] + next(imageData)[:3]]

            #8 bits make a byte
            for i in range(8):
                #if the bit is 1, make the pixel value odd, if 0 make it even
                if messageDataList[x][i] == '0' and pixels[i] % 2 != 0:
                    pixels[i] -= 1
                elif messageDataList[x][i] == '1' and pixels[i] % 2 == 0:
                    if pixels[i] != 0:
                        pixels[i] -= 1
                    else:
                        pixels[i] += 1

            #Next is to check if the message is done, if it is, we add a stop byte to the end of the message
            if i == messageDataLen - 1:
                if pixels[-1] % 2 == 0:
                    if pixels[-1] != 0:
                        pixels[-1] -= 1
                    else:
                        pixels[-1] += 1

            #Done three times since RGB values are three, we yield the modified pixel values
            yield tuple(pixels[:3])
            yield tuple(pixels[3:6])
            yield tuple(pixels[6:9])

    def encode(self):
        #Opens the image in read mode

        image = Image.open(self.imagePath, 'r')


        #Creates a copy of the image that will be the new image
        newImage = image.copy()


        #encodes the message into the image using the modifyPixel function

        a = newImage.size[0]

        for pixel in self.modifyPixel(newImage.getdata(), self.messageText):
            newImage.putpixel((a % newImage.size[0], a // newImage.size[0]), pixel)
            a += 1


        #Saves the new image with the encoded message to the output path.
        #Letting PIL infer the format from the file extension avoids passing
        #a bad format string (e.g. "JPG", which PIL doesn't recognize - it wants "JPEG").
        newImage.save(self.outputImagePath)



        




class PyStegDecoder():
    def __init__(self):

        self.outputMessagePath = None







