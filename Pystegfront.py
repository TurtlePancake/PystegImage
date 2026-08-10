import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import Pystegback  # Backend module (in progress) — see the "BACKEND CONNECTION POINT" comments below

from PIL import Image

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

IMAGE_FILETYPES = [
    ("Image files", "*.png *.bmp *.jpg *.jpeg *.tiff *.gif"),
    ("All files", "*.*"),
]
TEXT_FILETYPES = [
    ("Text files", "*.txt"),
    ("All files", "*.*"),
]

# Encoding is done with the lossless LSB method, so the output image must be
# saved in a lossless format (JPEG's compression would destroy the hidden bits).
OUTPUT_IMAGE_FILETYPES = [
    ("PNG image", "*.png"),
    ("Bitmap image", "*.bmp"),
]
OUTPUT_IMAGE_EXTENSIONS = {".png", ".bmp"}

PREVIEW_SIZE = (170, 170)

# -- Shared style constants (dark mode only) --------------------------------
CARD_FG = "gray16"
CARD_BORDER = "gray25"

STATUS_STYLES = {
    "info": {"fg_color": "gray20", "text_color": "gray90"},
    "pending": {"fg_color": "#4a3a12", "text_color": "#f5d67a"},
    "success": {"fg_color": "#1f3d29", "text_color": "#7fe0a0"},
    "error": {"fg_color": "#4a1f1f", "text_color": "#f28b82"},
}


class ImagePreview(ctk.CTkLabel):
    """A small square panel that shows a thumbnail of the selected image, or placeholder text."""

    def __init__(self, master):
        super().__init__(master, text="No image selected", width=PREVIEW_SIZE[0],
                          height=PREVIEW_SIZE[1], fg_color="gray22", corner_radius=12,
                          text_color="gray60")
        self._ctk_image = None

    def set_image_path(self, path: str):
        try:
            img = Image.open(path)
            img.thumbnail(PREVIEW_SIZE)
            self._ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self.configure(image=self._ctk_image, text="")
        except Exception:
            self._ctk_image = None
            self.configure(image=None, text="Preview unavailable")

    def clear(self):
        self._ctk_image = None
        self.configure(image=None, text="No image selected")


def make_card(parent, title: str):
    """Build a titled 'card' panel and return (card_frame, body_frame) so callers just fill body_frame."""
    card = ctk.CTkFrame(parent, fg_color=CARD_FG, corner_radius=14, border_width=1, border_color=CARD_BORDER)
    card.grid_columnconfigure(0, weight=1)

    header = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=14, weight="bold"), anchor="w")
    header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 2))

    body = ctk.CTkFrame(card, fg_color="transparent")
    body.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
    body.grid_columnconfigure(0, weight=1)

    return card, body


class EncodeTab(ctk.CTkFrame):
    """Encoding tab: cover image + secret message (typed or from a text file) + output path."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        # Variables sent to the backend
        self.cover_image_path = tk.StringVar()
        self.message_source = tk.StringVar(value="text")  # "text" or "file"
        self.message_text_file_path = tk.StringVar()
        self.output_image_path = tk.StringVar()

        self.grid_columnconfigure(0, weight=1)

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=0, column=0, sticky="ew")
        content.grid_columnconfigure(0, weight=1)

        # --- Cover image card ---
        image_card, image_body = make_card(content, "Cover Image")
        image_card.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        image_body.grid_columnconfigure(0, weight=1)

        self.cover_image_entry = ctk.CTkEntry(
            image_body, textvariable=self.cover_image_path, height=32,
            placeholder_text="Select an image to hide your message in...")
        self.cover_image_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(image_body, text="Browse", width=90, height=32,
                       command=self.browse_cover_image).grid(row=0, column=1)

        self.preview = ImagePreview(image_body)
        self.preview.grid(row=1, column=0, columnspan=2, pady=(8, 0))

        # --- Secret message card ---
        message_card, message_body = make_card(content, "Secret Message")
        message_card.grid(row=1, column=0, sticky="ew", pady=8)
        message_body.grid_columnconfigure(0, weight=1)

        self.message_toggle = ctk.CTkSegmentedButton(
            message_body, values=["Type Text", "Text File"],
            command=self.on_message_source_change)
        self.message_toggle.set("Type Text")
        self.message_toggle.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        # Container that swaps between the textbox and the file picker
        self.message_container = ctk.CTkFrame(message_body, fg_color="transparent")
        self.message_container.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.message_container.grid_columnconfigure(0, weight=1)

        self.message_textbox = ctk.CTkTextbox(self.message_container, height=80, corner_radius=8)
        self.message_textbox.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.message_file_entry = ctk.CTkEntry(
            self.message_container, textvariable=self.message_text_file_path, height=32,
            placeholder_text="Select a .txt file containing your message...")
        self.message_file_button = ctk.CTkButton(
            self.message_container, text="Browse", width=90, height=32,
            command=self.browse_message_file)

        self._show_text_input()

        # --- Output card ---
        output_card, output_body = make_card(content, "Save Encoded Image To")
        output_card.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        output_body.grid_columnconfigure(0, weight=1)

        self.output_path_entry = ctk.CTkEntry(
            output_body, textvariable=self.output_image_path, height=32,
            placeholder_text="Choose where the encoded image will be saved...")
        self.output_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(output_body, text="Browse", width=90, height=32,
                       command=self.browse_output_path).grid(row=0, column=1)

        # --- Encode button ---
        ctk.CTkButton(self, text="Encode Message", height=42, font=ctk.CTkFont(size=15, weight="bold"),
                       command=self.encode).grid(row=1, column=0, sticky="ew", pady=(12, 0))

    # -- UI callbacks --

    def on_message_source_change(self, selection: str):
        if selection == "Type Text":
            self.message_source.set("text")
            self._show_text_input()
        else:
            self.message_source.set("file")
            self._show_file_input()

    def _show_text_input(self):
        self.message_file_entry.grid_forget()
        self.message_file_button.grid_forget()
        self.message_textbox.grid(row=0, column=0, columnspan=2, sticky="ew")

    def _show_file_input(self):
        self.message_textbox.grid_forget()
        self.message_file_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.message_file_button.grid(row=0, column=1)

    def browse_cover_image(self):
        path = filedialog.askopenfilename(title="Select cover image", filetypes=IMAGE_FILETYPES)
        if path:
            self.cover_image_path.set(path)
            self.preview.set_image_path(path)

    def browse_message_file(self):
        path = filedialog.askopenfilename(title="Select message text file", filetypes=TEXT_FILETYPES)
        if path:
            self.message_text_file_path.set(path)

    def browse_output_path(self):
        default_name = "encoded_image.png"
        cover = self.cover_image_path.get()
        if cover:
            suffix = Path(cover).suffix.lower()
            suffix = suffix if suffix in OUTPUT_IMAGE_EXTENSIONS else ".png"
            default_name = f"{Path(cover).stem}_encoded{suffix}"
        path = filedialog.asksaveasfilename(
            title="Save encoded image as", defaultextension=".png",
            initialfile=default_name, filetypes=OUTPUT_IMAGE_FILETYPES)
        if not path:
            return
        if Path(path).suffix.lower() not in OUTPUT_IMAGE_EXTENSIONS:
            messagebox.showerror("Unsupported format",
                                  "The encoded image must be saved as PNG or BMP — "
                                  "other formats would corrupt the hidden message.")
            return
        self.output_image_path.set(path)

    def encode(self):
        # Gather everything the backend will need.
        cover_image_path = self.cover_image_path.get().strip()
        output_image_path = self.output_image_path.get().strip()
        source = self.message_source.get()

        if not cover_image_path:
            messagebox.showerror("Missing cover image", "Please select an image to encode into.")
            return
        if not output_image_path:
            messagebox.showerror("Missing output path", "Please choose where to save the encoded image.")
            return
        if Path(output_image_path).suffix.lower() not in OUTPUT_IMAGE_EXTENSIONS:
            messagebox.showerror("Unsupported format",
                                  "The encoded image must be saved as PNG or BMP — "
                                  "other formats would corrupt the hidden message.")
            return

        if source == "text":
            message = self.message_textbox.get("1.0", "end-1c")
            message_text_file_path = None
            if not message.strip():
                messagebox.showerror("Missing message", "Please type a message to hide.")
                return
        else:
            message = None
            message_text_file_path = self.message_text_file_path.get().strip()
            if not message_text_file_path:
                messagebox.showerror("Missing text file", "Please select a text file containing your message.")
                return

        payload = {
            "cover_image_path": cover_image_path,
            "message_source": source,       # "text" or "file"
            "message_text": message,        # set when message_source == "text"
            "message_text_file_path": message_text_file_path,  # set when message_source == "file"
            "output_image_path": output_image_path,
        }

        # ------------------------------------------------------------------
        # BACKEND CONNECTION POINT
        # This is where the frontend hands off to Pystegback.PyStegEncoder.
        # checkImageSize / OpenImage / convertToBinary still need a finished
        # encode() method wired up backend-side before this actually writes
        # a stego image — for now we just construct the encoder and report
        # that the backend logic isn't finished yet.
        # ------------------------------------------------------------------
        try:
            encoder = Pystegback.PyStegEncoder(
                imagePath=payload["cover_image_path"],
                messageSource=payload["message_source"],
                messageText=payload["message_text"],
                messageFilePath=payload["message_text_file_path"],
                outputImagePath=payload["output_image_path"],
            )
        except Exception as exc:
            messagebox.showerror("Backend error", f"Could not create the encoder:\n{exc}")
            self.app.set_status("Encoder failed to start.", kind="error")
            return

        self.app.set_status(f"Encoder created for {Path(output_image_path).name} — backend logic not finished yet.",
                             kind="pending")
        print("Encode payload:", payload)


        #If the encoder makes it here, it starts process one
        #First checks if the image is big enough to hold the text
        if encoder.checkImageSize() == False:
            messagebox.showerror("Image to small!", f"The image is too small to hold the message, try getting a bigger image")

        else:
            #If the image is big enough, it will convert the text to binary
            encoder.encode()



class DecodeTab(ctk.CTkFrame):
    """Decoding tab: stego image in, decoded message saved to a text file."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        self.stego_image_path = tk.StringVar()
        self.decoded_output_path = tk.StringVar()

        self.grid_columnconfigure(0, weight=1)

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=0, column=0, sticky="ew")
        content.grid_columnconfigure(0, weight=1)

        # --- Encoded image card ---
        image_card, image_body = make_card(content, "Encoded Image")
        image_card.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        image_body.grid_columnconfigure(0, weight=1)

        self.stego_image_entry = ctk.CTkEntry(
            image_body, textvariable=self.stego_image_path, height=32,
            placeholder_text="Select the image containing a hidden message...")
        self.stego_image_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(image_body, text="Browse", width=90, height=32,
                       command=self.browse_stego_image).grid(row=0, column=1)

        self.preview = ImagePreview(image_body)
        self.preview.grid(row=1, column=0, columnspan=2, pady=(8, 0))

        # --- Output card ---
        output_card, output_body = make_card(content, "Save Decoded Message To")
        output_card.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        output_body.grid_columnconfigure(0, weight=1)

        self.output_path_entry = ctk.CTkEntry(
            output_body, textvariable=self.decoded_output_path, height=32,
            placeholder_text="Choose where the decoded message will be saved...")
        self.output_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(output_body, text="Browse", width=90, height=32,
                       command=self.browse_output_path).grid(row=0, column=1)

        # --- Decode button ---
        ctk.CTkButton(self, text="Decode Message", height=42, font=ctk.CTkFont(size=15, weight="bold"),
                       command=self.decode).grid(row=1, column=0, sticky="ew", pady=(12, 0))

    def browse_stego_image(self):
        path = filedialog.askopenfilename(title="Select encoded image", filetypes=IMAGE_FILETYPES)
        if path:
            self.stego_image_path.set(path)
            self.preview.set_image_path(path)

    def browse_output_path(self):
        path = filedialog.asksaveasfilename(
            title="Save decoded message as", defaultextension=".txt",
            initialfile="decoded_message.txt", filetypes=TEXT_FILETYPES)
        if path:
            self.decoded_output_path.set(path)

    def decode(self):
        stego_image_path = self.stego_image_path.get().strip()
        decoded_output_path = self.decoded_output_path.get().strip()

        if not stego_image_path:
            messagebox.showerror("Missing image", "Please select an encoded image.")
            return
        if not decoded_output_path:
            messagebox.showerror("Missing output path", "Please choose where to save the decoded message.")
            return

        payload = {
            "stego_image_path": stego_image_path,
            "decoded_output_path": decoded_output_path,
        }

        # ------------------------------------------------------------------
        # BACKEND CONNECTION POINT
        # Pystegback.py only has a commented-out PyStegDecoder class so far.
        # Once it's implemented, this is where it gets called, e.g.:
        #
        #     decoder = Pystegback.PyStegDecoder()
        #     message = decoder.decode(payload["stego_image_path"])
        #     Path(payload["decoded_output_path"]).write_text(message)
        #
        # For now we just stage the payload so the UI can be wired up ahead
        # of the backend being ready.
        # ------------------------------------------------------------------
        self.app.set_status(f"Payload ready — backend not connected yet ({Path(decoded_output_path).name})",
                             kind="pending")
        print("Decode payload:", payload)


class SteganographyApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PystegImage")
        self.geometry("620x850")
        self.minsize(620, 850)
        self._center_on_screen(620, 850)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Header ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 6))

        ctk.CTkLabel(header, text="PystegImage", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(header, text="Hide and reveal secret messages inside images",
                     font=ctk.CTkFont(size=13), text_color="gray65").pack(anchor="w")

        # --- Tabs ---
        self.tabview = ctk.CTkTabview(self, corner_radius=14)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=20, pady=8)

        encode_tab = self.tabview.add("Encode")
        decode_tab = self.tabview.add("Decode")

        encode_tab.grid_columnconfigure(0, weight=1)
        encode_tab.grid_rowconfigure(0, weight=1)
        decode_tab.grid_columnconfigure(0, weight=1)
        decode_tab.grid_rowconfigure(0, weight=1)

        self.encode_frame = EncodeTab(encode_tab, self)
        self.encode_frame.grid(row=0, column=0, sticky="nsew")

        self.decode_frame = DecodeTab(decode_tab, self)
        self.decode_frame.grid(row=0, column=0, sticky="nsew")

        # --- Status bar ---
        self.status_bar = ctk.CTkFrame(self, corner_radius=10, fg_color=STATUS_STYLES["info"]["fg_color"])
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 16))
        self.status_label = ctk.CTkLabel(self.status_bar, text="Ready", anchor="w",
                                          text_color=STATUS_STYLES["info"]["text_color"])
        self.status_label.pack(fill="x", padx=12, pady=8)

    def _center_on_screen(self, width: int, height: int):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 3
        self.geometry(f"{width}x{height}+{x}+{y}")

    def set_status(self, message: str, kind: str = "info"):
        style = STATUS_STYLES.get(kind, STATUS_STYLES["info"])
        self.status_bar.configure(fg_color=style["fg_color"])
        self.status_label.configure(text=message, text_color=style["text_color"])


if __name__ == "__main__":
    app = SteganographyApp()
    app.mainloop()
