import fitz  # PyMuPDF
import os

from telegram import (
    Update,
    InputFile,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# ================= CONFIG =================
TOKEN = os.environ.get("BOT_TOKEN")  # setat în Railway
CHOICE = 1
last_file_path = ""

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Send a PDF file.\n\n"
        "✅ I will clean:\n"
        "- header above 'BILL OF LADING'\n"
        "- all 'Phone:' numbers\n"
        "- SuperDispatch links\n\n"
        "✏️ Then choose the company info to insert."
    )

# ================= HANDLE PDF =================
async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_file_path

    document = update.message.document
    file_name = document.file_name

    if not file_name.lower().endswith(".pdf"):
        await update.message.reply_text("❌ Please send a PDF file.")
        return ConversationHandler.END

    input_path = f"recv_{file_name}"
    cleaned_path = f"cleaned_{file_name}"

    tg_file = await document.get_file()
    await tg_file.download_to_drive(input_path)

    doc = fitz.open(input_path)

    for page in doc:
        # Remove header above BILL OF LADING
        areas = page.search_for("BILL OF LADING")
        if areas:
            rect = fitz.Rect(0, 0, page.rect.width, areas[0].y0)
            page.add_redact_annot(rect, fill=(1, 1, 1))

        # Remove Phone:
        for area in page.search_for("Phone:"):
            page.add_redact_annot(
                fitz.Rect(area.x0, area.y0 - 1, area.x1 + 130, area.y1 + 3),
                fill=(1, 1, 1),
            )

        # Remove superdispatch.com
        for area in page.search_for("superdispatch.com"):
            page.add_redact_annot(
                fitz.Rect(35, area.y0 - 10, page.rect.width - 35, area.y1 + 15),
                fill=(1, 1, 1),
            )

        page.apply_redactions()

    doc.save(cleaned_path)
    doc.close()

    last_file_path = cleaned_path

    keyboard = [["FMK GROUP INC"], ["BM 5 EXPRESS LLC"]]
    await update.message.reply_text(
        "📌 Choose the company info to insert:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True),
    )

    return CHOICE

# ================= HANDLE COMPANY CHOICE =================
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_file_path

    text = update.message.text.upper()

    if "FMK" in text:
        company_text = (
            "FMK GROUP INC\n"
            "33 E GRAND AVE UNIT 42\n"
            "FOX LAKE, IL 60020\n"
            "USDOT: 4252237\n"
            "MC: 1738338"
        )
    elif "BM" in text:
        company_text = (
            "BM 5 EXPRESS LLC\n"
            "3507 COURT ST #1009\n"
            "PEKIN, IL 61554\n"
            "USDOT: 4252114\n"
            "MC: 1721817"
        )
    else:
        await update.message.reply_text("❌ Unknown selection.")
        return ConversationHandler.END

    doc = fitz.open(last_file_path)
    for page in doc:
        page.insert_text((40, 40), company_text, fontsize=12, color=(0, 0, 0))

    final_path = last_file_path.replace("cleaned_", "final_")
    doc.save(final_path)
    doc.close()

    # ================= SEND PDF BACK (CORECT) =================
    with open(final_path, "rb") as pdf:
        await update.message.reply_document(
            document=InputFile(
                pdf,
                filename=os.path.basename(final_path)
            ),
            mime_type="application/pdf",
            caption="📄 PDF processed successfully",
            reply_markup=ReplyKeyboardRemove(),
        )

    # Cleanup (opțional dar recomandat)
    try:
        os.remove(final_path)
        os.remove(last_file_path)
    except:
        pass

    return ConversationHandler.END

# ================= MAIN =================
def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not set!")

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Document.PDF, handle_pdf),
        ],
        states={
            CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice)]
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)

    print("✅ Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
