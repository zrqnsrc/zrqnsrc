import telebot
from io import BytesIO
import re

# Token API bot Telegram Anda
API_TOKEN = '6627720006:AAEFN5Rdv4um-Nsi0V7vRNWlbd0ShkMf200'
bot = telebot.TeleBot(API_TOKEN)

# Variabel global untuk menyimpan informasi sesi
user_data = {}

# Fungsi untuk mengekstrak nomor telepon dari teks
def extract_phone_number(text):
    cleaned_number = re.sub(r'\D', '', text)  # Hapus semua karakter non-digit
    return f"+{cleaned_number}" if cleaned_number else None

# Fungsi untuk membuat kontak dalam format VCF versi 3.0
def create_vcf(name, phone_number):
    vcf_content = (
        "BEGIN:VCARD\n"
        "VERSION:3.0\n"
        f"N:{name};;;\n"
        f"FN:{name}\n"
        f"TEL;TYPE=CELL:{phone_number}\n"
        "END:VCARD"
    )
    return vcf_content

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = telebot.types.InlineKeyboardMarkup()
    convert_button = telebot.types.InlineKeyboardButton('Convert File', callback_data='convert')
    split_button = telebot.types.InlineKeyboardButton('Pecah File', callback_data='split')
    admin_navy_button = telebot.types.InlineKeyboardButton('File Admin/Navy', callback_data='admin_navy')
    markup.add(convert_button, split_button)
    markup.add(admin_navy_button)
    bot.reply_to(message, "Pilih opsi yang Anda inginkan:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ['convert', 'split', 'admin_navy'])
def handle_option_selection(call):
    chat_id = call.message.chat.id
    user_data[chat_id] = {'option': call.data, 'files': []}  # Inisialisasi dengan list kosong untuk file
    
    if call.data == 'admin_navy':
        markup = telebot.types.InlineKeyboardMarkup()
        admin_button = telebot.types.InlineKeyboardButton('Admin Saja', callback_data='admin')
        navy_button = telebot.types.InlineKeyboardButton('Navy Saja', callback_data='navy')
        combined_button = telebot.types.InlineKeyboardButton('Gabung Admin/Navy', callback_data='combined_admin_navy')
        markup.add(admin_button, navy_button)
        markup.add(combined_button)
        bot.edit_message_text("Pilih sub-opsi yang Anda inginkan:", chat_id, call.message.message_id, reply_markup=markup)
    else:
        bot.delete_message(chat_id, call.message.message_id)
        bot.send_message(chat_id, "Kirim file teks yang ingin Anda proses. Setelah mengirimkan semua file, balas dengan format:\n\n"
                                  "'nama kontak, ya/tidak, nama file'. (untuk convert)\n"
                                  "'nama kontak, ya/tidak, jumlah per file, nama file'. (untuk split)")

@bot.callback_query_handler(func=lambda call: call.data in ['admin', 'navy', 'combined_admin_navy'])
def handle_admin_navy_selection(call):
    chat_id = call.message.chat.id
    user_data[chat_id]['sub_option'] = call.data
    bot.delete_message(chat_id, call.message.message_id)
    bot.send_message(chat_id, "Silakan kirimkan nomor-nomor sesuai format yang diminta.")

@bot.message_handler(content_types=['document'])
def handle_document(message):
    chat_id = message.chat.id

    if chat_id not in user_data or 'option' not in user_data[chat_id]:
        bot.reply_to(message, "Silakan pilih opsi terlebih dahulu dengan /start.")
        return

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    file_extension = message.document.file_name.split('.')[-1].lower()

    if file_extension != 'txt':
        bot.reply_to(message, "Hanya file teks (.txt) yang didukung saat ini.")
        return

    # Tambahkan konten file ke dalam list di user_data
    user_data[chat_id]['files'].append({
        'name': message.document.file_name,
        'content': downloaded_file,
        'message_id': message.message_id  # Menyimpan ID pesan untuk referensi
    })
    # Mengirim pesan bahwa file telah diterima dan meminta nama file output
    bot.reply_to(message, f"File {message.document.file_name} telah diterima ✅.\nSilakan balas dengan nama file output yang diinginkan.")

@bot.message_handler(regexp=r'^.*,.+,.*$')
def handle_response(message):
    chat_id = message.chat.id
    if chat_id not in user_data or not user_data[chat_id]['files']:
        bot.reply_to(message, "Format tidak valid atau file tidak ada.")
        return

    response = message.text.split(',')
    option = user_data[chat_id].get('option')

    if option == 'convert' and len(response) != 3:
        bot.reply_to(message, "Format balasan tidak valid. Harap gunakan format:\n"
                              "'nama kontak, ya/tidak, nama file'.")
        return
    elif option == 'split' and len(response) != 4:
        bot.reply_to(message, "Format balasan tidak valid. Harap gunakan format:\n"
                              "'nama kontak, ya/tidak, jumlah per file, nama file'.")
        return

    contact_name = response[0].strip()
    numbering = response[1].strip().lower() == 'ya'
    output_filename = response[-1].strip()

    for index, file_info in enumerate(user_data[chat_id]['files'], start=1):
        file_content = file_info['content']
        original_filename = file_info['name']
        message_id = file_info['message_id']
        vcf_content_list = []
        valid_numbers = []

        # Proses setiap file TXT
        lines = file_content.decode('utf-8').splitlines()
        for line in lines:
            phone_number = extract_phone_number(line)
            if phone_number:
                valid_numbers.append(phone_number)

        if option == 'convert':
            for i, phone_number in enumerate(valid_numbers, start=1):
                contact_name_with_number = f"{contact_name}_{i}" if numbering else contact_name
                vcf_content = create_vcf(contact_name_with_number, phone_number)
                vcf_content_list.append(vcf_content)

            if vcf_content_list:
                vcf_data = "\n".join(vcf_content_list)
                vcf_file = BytesIO(vcf_data.encode('utf-8'))
                # Menggunakan nama file output yang ditentukan pengguna
                if len(user_data[chat_id]['files']) > 1:
                    vcf_file.name = f'{output_filename}_part_{index}.vcf'
                else:
                    vcf_file.name = f'{output_filename}.vcf'
                bot.send_document(chat_id, vcf_file)

                # Mengirim pesan balasan dengan detail konversi
                bot.reply_to(message, f"File asli: {original_filename}\nJumlah kontak: {len(valid_numbers)}", reply_to_message_id=message_id)
            else:
                bot.send_message(chat_id, f"Tidak ada data yang valid untuk dikonversi dalam file {original_filename}.")

        elif option == 'split':
            total_numbers = len(valid_numbers)
            if total_numbers == 0:
                bot.send_message(chat_id, f"Tidak ada data yang valid untuk diproses dalam file {original_filename}.")
                continue

            # Membagi kontak menjadi beberapa bagian sesuai jumlah per file
            try:
                split_count = int(response[2].strip())  # Jumlah kontak per file
                remaining_contacts = total_numbers % split_count  # Sisa kontak yang tidak terbagi rata
                for idx, start in enumerate(range(0, total_numbers, split_count), start=1):
                    part_numbers = valid_numbers[start:start + split_count]
                    vcf_content_list = []
                    for i, phone_number in enumerate(part_numbers, start=1):
                        contact_name_with_number = f"{contact_name}_{i}" if numbering else contact_name
                        vcf_content = create_vcf(contact_name_with_number, phone_number)
                        vcf_content_list.append(vcf_content)

                    if vcf_content_list:
                        vcf_data = "\n".join(vcf_content_list)
                        vcf_file = BytesIO(vcf_data.encode('utf-8'))
                        vcf_file.name = f'{output_filename}_part_{idx}.vcf'  # Menggunakan format nama file yang diinginkan
                        bot.send_document(chat_id, vcf_file)

                # Mengirim pesan balasan dengan detail pembagian file
                detail_message = f"File asli: {original_filename}\nJumlah kontak per file: {split_count}\n"
                if remaining_contacts > 0:
                    detail_message += f"Sisa kontak yang tidak terbagi rata: {remaining_contacts}"
                bot.reply_to(message, detail_message, reply_to_message_id=message_id)
            except ValueError:
                bot.send_message(chat_id, "Jumlah per file harus berupa angka.")

    bot.send_message(chat_id, "Semua file telah diproses dan dikirim.")

    # Hapus data pengguna setelah selesai
    if chat_id in user_data:
        del user_data[chat_id]

@bot.message_handler(regexp=r'^(admin|navy)\n\d+')
def handle_contact_entry(message):
    chat_id = message.chat.id
    sub_option = user_data[chat_id].get('sub_option')
    
    if sub_option == 'admin' or sub_option == 'navy':
        lines = message.text.splitlines()[1:]  # Mengabaikan baris pertama yang merupakan "admin" atau "navy"
        vcf_content_list = []
        for i, line in enumerate(lines, start=1):
            phone_number = extract_phone_number(line)
            if phone_number:
                contact_name = f"{sub_option.capitalize()}_{i}"
                vcf_content = create_vcf(contact_name, phone_number)
                vcf_content_list.append(vcf_content)
        
        if vcf_content_list:
            vcf_data = "\n".join(vcf_content_list)
            vcf_file = BytesIO(vcf_data.encode('utf-8'))
            vcf_file.name = f"{sub_option}.vcf"
            bot.send_document(chat_id, vcf_file)
            bot.send_message(chat_id, f"File VCF '{sub_option}.vcf' telah dibuat dan dikirim.")
        else:
            bot.send_message(chat_id, "Tidak ada nomor valid yang ditemukan.")

    elif sub_option == 'combined_admin_navy':
        vcf_content_list = []
        current_section = None
        admin_count = 0
        navy_count = 0
        lines = message.text.splitlines()
        
        for line in lines:
            if line.lower() in ['admin', 'navy']:
                current_section = line.lower()
            else:
                phone_number = extract_phone_number(line)
                if phone_number:
                    if current_section == 'admin':
                        admin_count += 1
                        contact_name = f"Admin_{admin_count}"
                    elif current_section == 'navy':
                        navy_count += 1
                        contact_name = f"Navy_{navy_count}"
                    vcf_content = create_vcf(contact_name, phone_number)
                    vcf_content_list.append(vcf_content)

        if vcf_content_list:
            vcf_data = "\n".join(vcf_content_list)
            vcf_file = BytesIO(vcf_data.encode('utf-8'))
            vcf_file.name = "Combined_Admin_Navy.vcf"
            bot.send_document(chat_id, vcf_file)
            bot.send_message(chat_id, "File VCF 'Combined_Admin_Navy.vcf' telah dibuat dan dikirim.")
        else:
            bot.send_message(chat_id, "Tidak ada nomor valid yang ditemukan.")

# Mulai polling
bot.polling()
