import os
import fitz  # PyMuPDF
from telegram import Update, InputFile, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)

# === TOKEN din variabila de mediu ===
TOKEN = os.getenv("TOKEN")

# === STATES ===
CHOICE = 1
last_file_path = ""

# === START ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📥 /start received from user.")
    await update.message.reply_text(
        "📄 Отправьте PDF файл.\n"
        "✅ Я удалю заголовок (до 'BILL OF LADING'), все номера телефонов и ссылки SuperDispatch.\n"
        "✏️ Затем выберите информацию о компании, которую нужно вставить на каждой странице."
    )

# === HANDLE PDF ===
async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_file_path
    document = update.message.document
    file_name = document.file_name
    input_path = f"recv_{file_name}"
    output_path = f"cleaned_{file_name}"

    print(f"📄 Received PDF: {file_name}")
    await document.get_file().download_to_drive(input_path)

    doc = fitz.open(input_path)

    for page_num, page in enumerate(doc):
        print(f"📄 Processing page {page_num + 1}...")

        # 🧼 Remove header
        areas = page.search_for("BILL OF LADING")
        if areas:
            y_cut = areas[0].y0
            rect = fitz.Rect(0, 0, page.rect.width, y_cut)
            page.add_redact_annot(rect, fill=(1, 1, 1))

        # 🧼 Remove all Phone:
        phone_areas = page.search_for("Phone:")
        for area in phone_areas:
            redact_box = fitz.Rect(area.x0, area.y0 - 1, area.x1 + 130, area.y1 + 3)
            page.add_redact_annot(redact_box, fill=(1, 1, 1))

        # 🧼 Remove superdispatch.com
        link_areas = page.search_for("superdispatch.com")
        for area in link_areas:
            left_margin = 35
            right_margin = 35
            full_line = fitz.Rect(left_margin, area.y0 - 10, page.rect.width - right_margin, area.y1 + 15)
            page.add_redact_annot(full_line, fill=(1, 1, 1))

        page.apply_redactions()

    doc.save(output_path)
    doc.close()

    print("🧼 All pages cleaned.")
    last_file_path = output_path

    # ✅ Reply keyboard cu companii
    keyboard = [
        ["FMK GROUP INC"],
        ["BM 5 EXPRESS LLC"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    print("📌 Sending keyboard to user")
    await update.message.reply_text("📌 Выберите компанию:", reply_markup=reply_markup)

    return CHOICE

# === HANDLE CHOICE ===
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    print(f"📌 User selected: {choice}")
    choice_upper = choice.upper()

    if "FMK" in choice_upper:
        return await insert_predefined_text(update, context, "FMK")
    elif "BM" in choice_upper:
        return await insert_predefined_text(update, context, "BM")
    else:
        await update.message.reply_text("❌ Неизвестный выбор.")
        return ConversationHandler.END

# === INSERT PREDEFINED TEXT ON ALL PAGES ===
async def insert_predefined_text(update: Update, context: ContextTypes.DEFAULT_TYPE, company_key):
    global last_file_path

    if company_key == "FMK":
        print("✍️ Inserting FMK GROUP INC")
        predefined = (
            "FMK GROUP INC\n"
            "33 E GRAND AVE UNIT 42\n"
            "FOX LAKE, IL   60020\n"
            "USDOT:  4252237\n"
            "MC: 1738338"
        )
    elif company_key == "BM":
        print("✍️ Inserting BM 5 EXPRESS LLC")
        predefined = (
            "BM 5 EXPRESS LLC\n"
            "3507 COURT ST #1009\n"
            "PEKIN, IL   61554\n"
            "USDOT: 4252114\n"
            "MC: 1721817"
        )
    else:
        await update.message.reply_text("❌ Неизвестная компания.")
        return ConversationHandler.END

    doc = fitz.open(last_file_path)
    for i, page in enumerate(doc):
        print(f"✍️ Inserting on page {i + 1}")
        page.insert_text((40, 40), predefined, fontsize=12, color=(0, 0, 0))

    final_path = last_file_path.replace("cleaned_", "final_")
    doc.save(final_path)
    doc.close()

    try:
        with open(final_path, "rb") as f:
            await update.message.reply_document(document=InputFile(f, filename=final_path))
            print(f"✅ Sent file: {final_path}")
        await update.message.reply_text("✅ Файл готов и отправлен.")
    except Exception as e:
        print(f"❌ Error sending PDF: {e}")
        await update.message.reply_text("❌ Не удалось отправить изменённый PDF.")

    return ConversationHandler.END

# === MAIN ===
def main():
    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Document.PDF, handle_pdf)
        ],
        states={
            CHOICE: [MessageHandler(filters.TEXT & (~filters.COMMAND), handle_choice)]
        },
        fallbacks=[]
    )

    application.add_handler(conv_handler)

    print("✅ Bot is running. Waiting for PDF files...")
    application.run_polling()

if __name__ == "__main__":
    main()
