import tkinter as tk
from tkinter import messagebox, ttk
import mysql.connector


class HotelReservation:
    def __init__(self, root):
        self.root = root
        self.setup_styles()
        self.setup_window()

        # Database configuration - change password if you have one
        self.db_config = {
            "host": "localhost",
            "user": "root",
            "password": "",  # set your MySQL password here if needed
            "database": "hotel_reservation_system"
        }

        # Attempt to load rooms/services from DB
        self.rooms = {}
        self.services = {}
        self._initial_db_load()

        # pending reservation state across screens
        self.pending = {
            "name": None,
            "phone": None,
            "nights": None,
            "room": None,
            "services": [],
            "payment": None,
            "total": 0.0
        }

        # Start at welcome screen
        self.show_welcome()

    # ---------- Setup & styles ----------
    def setup_styles(self):
        self.colors = {
            'primary': '#2C3E50',      # Dark blue-gray
            'secondary': '#3498DB',    # Bright blue
            'accent': '#E74C3C',       # Red for danger / Cancel Reservation
            'success': '#27AE60',      # Green for confirm
            'light': '#ECF0F1',        # Page background
            'white': '#FFFFFF',
            'dark_text': '#2C3E50',
            'card': '#FFFFFF',
            'border': '#BDC3C7'
        }
        self.fonts = {
            'heading': ('Segoe UI', 20, 'bold'),
            'subheading': ('Segoe UI', 16, 'bold'),
            'body': ('Segoe UI', 11),
            'body_bold': ('Segoe UI', 11, 'bold'),
            'button': ('Segoe UI', 10, 'bold')
        }

    def setup_window(self):
        self.root.title("LitHo Hotel - Hotel Reservation System")
        self.root.geometry("1000x750")
        self.root.configure(bg=self.colors['light'])
        self.root.resizable(True, True)
        # center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (1000 // 2)
        y = (self.root.winfo_screenheight() // 2) - (750 // 2)
        self.root.geometry(f"1000x750+{x}+{y}")

    # ---------- Database helpers ----------
    def connect(self):
        try:
            return mysql.connector.connect(**self.db_config)
        except mysql.connector.Error as e:
            # show error to user when a DB operation requires it
            messagebox.showerror("Database Error", f"Connection failed: {str(e)}")
            return None

    def try_connect_silent(self):
        """Try to connect without showing a messagebox (returns (conn, err))"""
        try:
            conn = mysql.connector.connect(**self.db_config)
            return conn, None
        except mysql.connector.Error as e:
            return None, str(e)

    def _initial_db_load(self):
        """Try connecting and loading rooms/services on startup silently."""
        conn, err = self.try_connect_silent()
        if conn:
            conn.close()
            self.rooms = self.load_rooms()
            self.services = self.load_services()
        else:
            self.rooms = {}
            self.services = {}

    def load_rooms(self):
        conn = self.connect()
        if not conn:
            return {}
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM rooms")
            rows = cursor.fetchall()
            result = {}
            for r in rows:
                room_type = r.get('room_type')
                result[room_type] = {
                    'id': r.get('room_id'),
                    'price': float(r.get('price')) if r.get('price') is not None else 0.0,
                    'available': int(r.get('available')) if r.get('available') is not None else 0
                }
            return result
        except mysql.connector.Error as e:
            messagebox.showerror("Database Error", f"Failed to load rooms: {str(e)}")
            return {}
        finally:
            conn.close()

    def load_services(self):
        conn = self.connect()
        if not conn:
            return {}
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM services")
            rows = cursor.fetchall()
            result = {}
            for s in rows:
                result[s.get('name')] = float(s.get('price')) if s.get('price') is not None else 0.0
            return result
        except mysql.connector.Error as e:
            messagebox.showerror("Database Error", f"Failed to load services: {str(e)}")
            return {}
        finally:
            conn.close()

    def add_reservation(self, name, phone, room, nights, services, total, payment):
        conn = self.connect()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            # insert guest
            cursor.execute("INSERT INTO guests (name, phone) VALUES (%s, %s)", (name, phone))
            guest_id = cursor.lastrowid
            # insert reservation
            cursor.execute(
                """INSERT INTO reservations (guest_id, room_id, nights, services, total, payment)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (guest_id, self.rooms[room]['id'], nights, ",".join(services), total, payment)
            )
            # update availability
            cursor.execute("UPDATE rooms SET available = available - 1 WHERE room_id = %s", (self.rooms[room]['id'],))
            conn.commit()
            # refresh local cache
            self.rooms = self.load_rooms()
            return True
        except mysql.connector.Error as e:
            conn.rollback()
            messagebox.showerror("Database Error", f"Failed to add reservation: {str(e)}")
            return False
        finally:
            conn.close()

    def get_reservations(self):
        conn = self.connect()
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.reservation_id, g.name, g.phone, rm.room_type, r.nights, r.services, r.total, r.payment
                FROM reservations r
                LEFT JOIN guests g ON r.guest_id = g.guest_id
                LEFT JOIN rooms rm ON r.room_id = rm.room_id
                ORDER BY r.created_at DESC
            """)
            rows = cursor.fetchall()
            return rows
        except mysql.connector.Error as e:
            messagebox.showerror("Database Error", f"Failed to retrieve reservations: {str(e)}")
            return []
        finally:
            conn.close()

    def delete_reservation(self, res_id):
        conn = self.connect()
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            # return room availability (if possible)
            cursor.execute("SELECT room_id FROM reservations WHERE reservation_id = %s", (res_id,))
            row = cursor.fetchone()
            if row and row[0]:
                cursor.execute("UPDATE rooms SET available = available + 1 WHERE room_id = %s", (row[0],))
            cursor.execute("DELETE FROM reservations WHERE reservation_id = %s", (res_id,))
            conn.commit()
            # refresh local cache so future Room Selection shows updated availability
            self.rooms = self.load_rooms()
            return True
        except mysql.connector.Error as e:
            conn.rollback()
            messagebox.showerror("Database Error", f"Failed to delete reservation: {str(e)}")
            return False
        finally:
            conn.close()

    # ---------- UI Helpers ----------
    def clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def create_card_frame(self, parent, title=None):
        card = tk.Frame(parent, bg=self.colors['card'], relief='solid', bd=1)
        card.pack(fill='both', expand=True, padx=20, pady=10)
        content = tk.Frame(card, bg=self.colors['card'])
        if title:
            title_frame = tk.Frame(card, bg=self.colors['primary'], height=50)
            title_frame.pack(fill='x')
            title_frame.pack_propagate(False)
            tk.Label(title_frame, text=title, font=self.fonts['subheading'],
                     bg=self.colors['primary'], fg=self.colors['white']).pack(expand=True)
        content.pack(fill='both', expand=True, padx=20, pady=20)
        return card, content

    def create_input_group(self, parent, label_text, entry_width=25):
        frame = tk.Frame(parent, bg=self.colors['card'])
        frame.pack(fill='x', pady=8)
        lbl = tk.Label(frame, text=label_text, font=self.fonts['body_bold'], bg=self.colors['card'], fg=self.colors['dark_text'])
        lbl.pack(anchor='w')
        entry = tk.Entry(frame, font=self.fonts['body'], width=entry_width, relief='solid', bd=1)
        entry.pack(anchor='w', pady=(2,0))
        return frame, lbl, entry

    def create_hotelreservation_button(self, parent, text, command, style='primary', width=200):
        if style == 'primary':
            bg = self.colors['primary']; fg = self.colors['white']
        elif style == 'secondary':
            bg = self.colors['light']; fg = self.colors['dark_text']
        elif style == 'success':
            bg = self.colors['success']; fg = self.colors['white']
        elif style == 'danger':
            bg = self.colors['accent']; fg = self.colors['white']
        elif style == 'light':
            bg = self.colors['light']; fg = self.colors['dark_text']
        else:
            bg = self.colors['secondary']; fg = self.colors['white']

        btn = tk.Button(parent, text=text, command=command, font=self.fonts['button'], bg=bg, fg=fg,
                        relief='flat', bd=0, padx=20, pady=10, cursor='hand2', width=width//8)
        btn.pack(pady=8)
        # simple hover effect
        def on_enter(e):
            try:
                btn.configure(bg=self.lighten_color(bg))
            except Exception:
                pass
        def on_leave(e):
            try:
                btn.configure(bg=bg)
            except Exception:
                pass
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def lighten_color(self, color):
        if color.startswith('#'):
            color = color[1:]
        rgb = (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))
        lighter = tuple(min(255, int(c*1.1)) for c in rgb)
        return f"#{lighter[0]:02x}{lighter[1]:02x}{lighter[2]:02x}"

    def create_radio_group(self, parent, title, options, variable):
        frame = tk.Frame(parent, bg=self.colors['card'])
        frame.pack(fill='x', pady=10)
        tk.Label(frame, text=title, font=self.fonts['body_bold'], bg=self.colors['card'], fg=self.colors['dark_text']).pack(anchor='w', pady=(0,5))
        for opt in options:
            tk.Radiobutton(frame, text=opt, variable=variable, value=opt, font=self.fonts['body'],
                           bg=self.colors['card'], fg=self.colors['dark_text'], selectcolor=self.colors['light']).pack(anchor='w', padx=10)
        return frame

    def create_checkbox_group(self, parent, title, options):
        frame = tk.Frame(parent, bg=self.colors['card'])
        frame.pack(fill='x', pady=10)
        tk.Label(frame, text=title, font=self.fonts['body_bold'], bg=self.colors['card'], fg=self.colors['dark_text']).pack(anchor='w', pady=(0,5))
        vars_map = {}
        for name, price in options.items():
            v = tk.IntVar()
            tk.Checkbutton(frame, text=f"{name} - ₱{price}", variable=v, font=self.fonts['body'],
                           bg=self.colors['card'], fg=self.colors['dark_text']).pack(anchor='w', padx=10)
            vars_map[name] = v
        return frame, vars_map

    # ---------- Cancel behavior & pending reset ----------
    def reset_pending(self):
        self.pending = {
            "name": None,
            "phone": None,
            "nights": None,
            "room": None,
            "services": [],
            "payment": None,
            "total": 0.0
        }

    def confirm_cancel(self, current_toplevel=None):
        """
        Confirmation for cancelling reservation flow. If confirmed, clear pending and return to home.
        If current_toplevel is provided (a Toplevel window), it will be destroyed before returning home.
        """
        if messagebox.askyesno("Cancel Reservation", "Are you sure you want to cancel this reservation and return to the Home Page?"):
            # destroy provided Toplevel if present
            try:
                if current_toplevel is not None:
                    current_toplevel.destroy()
            except Exception:
                pass
            self.reset_pending()
            # reload rooms/services from DB to ensure consistent state
            self.rooms = self.load_rooms()
            self.services = self.load_services()
            self.show_welcome()

    # ---------- Main screens ----------
    def show_welcome(self):
        self.clear_window()
        main_frame = tk.Frame(self.root, bg=self.colors['light'])
        main_frame.pack(fill='both', expand=True)

        header_frame = tk.Frame(main_frame, bg=self.colors['primary'], height=200)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        tk.Label(header_frame, text="LitHo Hotel", font=('Segoe UI', 36, 'bold'), bg=self.colors['primary'], fg=self.colors['white']).pack(expand=True, pady=(40, 10))
        tk.Label(header_frame, text="by: Christen Jefferson Escollar", font=('Segoe UI', 14), bg=self.colors['primary'], fg=self.colors['white']).pack()

        content_frame = tk.Frame(main_frame, bg=self.colors['light'])
        content_frame.pack(fill='both', expand=True, pady=50)

        button_frame = tk.Frame(content_frame, bg=self.colors['light'])
        button_frame.pack(expand=True)

        self.create_hotelreservation_button(button_frame, "🏨 Make Reservation", self.guest_information, 'primary', 300)
        self.create_hotelreservation_button(button_frame, "📋 Staff - View Reservations", self.view_reservations, 'secondary', 300)

    def guest_information(self):
        self.clear_window()
        main_frame = tk.Frame(self.root, bg=self.colors['light'])
        main_frame.pack(fill='both', expand=True)

        header_frame = tk.Frame(main_frame, bg=self.colors['secondary'], height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        tk.Label(header_frame, text="Make a Reservation", font=self.fonts['subheading'], bg=self.colors['secondary'], fg=self.colors['white']).pack(expand=True)

        content_frame = tk.Frame(main_frame, bg=self.colors['light'])
        content_frame.pack(fill='both', expand=True, padx=20, pady=50)

        guest_card, guest_content = self.create_card_frame(content_frame, "Guest Information")
        guest_card.pack(pady=50)
        guest_content.configure(width=500)

        _, _, self.name_entry = self.create_input_group(guest_content, "Full Name:", 40)
        _, _, self.phone_entry = self.create_input_group(guest_content, "Phone Number:", 40)
        _, _, self.nights_entry = self.create_input_group(guest_content, "Number of Nights:", 40)

        button_frame = tk.Frame(content_frame, bg=self.colors['light'])
        button_frame.pack(pady=30)
        container = tk.Frame(button_frame, bg=self.colors['light'])
        container.pack()
        self.create_hotelreservation_button(container, "→ Proceed to Room Selection", self.room_selection, 'success', 250)
        # Cancel Reservation goes to home (with confirm)
        self.create_hotelreservation_button(container, "Cancel Reservation", lambda: self.confirm_cancel(), 'danger', 250)

    def room_selection(self):
        # Validate inputs first
        name = self.name_entry.get().strip()
        phone = self.phone_entry.get().strip()
        nights = self.nights_entry.get().strip()

        if not name:
            messagebox.showwarning("Input Required", "Please enter your full name.")
            return
        if not phone or not phone.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            messagebox.showwarning("Invalid Input", "Please enter a valid phone number.")
            return
        if not nights.isdigit() or int(nights) <= 0:
            messagebox.showwarning("Invalid Input", "Number of nights must be a positive number.")
            return

        self.pending['name'] = name
        self.pending['phone'] = phone
        self.pending['nights'] = int(nights)
        self.pending['room'] = None
        self.pending['services'] = []
        self.pending['payment'] = None
        self.pending['total'] = 0.0

        # refresh rooms/services (in case availability changed)
        self.rooms = self.load_rooms()
        self.services = self.load_services()

        self.clear_window()
        main_frame = tk.Frame(self.root, bg=self.colors['light'])
        main_frame.pack(fill='both', expand=True)

        header_frame = tk.Frame(main_frame, bg=self.colors['secondary'], height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        tk.Label(header_frame, text="Room Selection & Services", font=self.fonts['subheading'], bg=self.colors['secondary'], fg=self.colors['white']).pack(expand=True)

        content_frame = tk.Frame(main_frame, bg=self.colors['light'])
        content_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Room card
        room_card, room_content = self.create_card_frame(content_frame, "Room Selection")
        self.room_choice = tk.StringVar(value="")

        if not self.rooms:
            info = tk.Label(room_content, text="No rooms found. You can Test DB or Load Sample data to continue.", bg=self.colors['card'], fg=self.colors['dark_text'], font=self.fonts['body'])
            info.pack(anchor='w', pady=(5, 10))
            row = tk.Frame(room_content, bg=self.colors['card'])
            row.pack(anchor='w', pady=5)
            tk.Button(row, text="Test DB Connection", command=self._on_test_db, bg=self.colors['secondary'], fg=self.colors['white'], relief='flat', padx=8, pady=6).pack(side='left', padx=5)
            tk.Button(row, text="Load Sample Rooms", command=self._load_sample_data, bg=self.colors['success'], fg=self.colors['white'], relief='flat', padx=8, pady=6).pack(side='left', padx=5)
        else:
            tk.Label(room_content, text="Select Room Type:", font=self.fonts['body_bold'], bg=self.colors['card'], fg=self.colors['dark_text']).pack(anchor='w', pady=(0,5))
            for room_name, details in self.rooms.items():
                display = f"{room_name} - ₱{details['price']}/night (Available: {details['available']})"
                tk.Radiobutton(room_content, text=display, variable=self.room_choice, value=room_name, font=self.fonts['body'], bg=self.colors['card'], fg=self.colors['dark_text'], selectcolor=self.colors['light']).pack(anchor='w', padx=10, pady=2)

        # Services card
        services_card, services_content = self.create_card_frame(content_frame, "Additional Services")
        self.service_vars = {}
        if not self.services:
            info = tk.Label(services_content, text="No services found. Use Test DB or Load Sample Rooms.", bg=self.colors['card'], fg=self.colors['dark_text'], font=self.fonts['body'])
            info.pack(anchor='w', pady=(5, 10))
        else:
            tk.Label(services_content, text="Select Extra Services:", font=self.fonts['body_bold'], bg=self.colors['card'], fg=self.colors['dark_text']).pack(anchor='w', pady=(0,5))
            for sname, sprice in self.services.items():
                var = tk.IntVar()
                tk.Checkbutton(services_content, text=f"{sname} - ₱{sprice}", variable=var, font=self.fonts['body'], bg=self.colors['card'], fg=self.colors['dark_text']).pack(anchor='w', padx=10, pady=2)
                self.service_vars[sname] = var

        # Live total preview
        preview = tk.Frame(content_frame, bg=self.colors['light'])
        preview.pack(fill='x', pady=(8,0))
        self.total_preview_label = tk.Label(preview, text="Total Preview: ₱0.00", font=self.fonts['body_bold'], bg=self.colors['light'], fg=self.colors['dark_text'])
        self.total_preview_label.pack(anchor='e', padx=10)

        # Bind simple traces
        self._bind_preview_traces()

        # Buttons
        button_frame = tk.Frame(content_frame, bg=self.colors['light'])
        button_frame.pack(pady=20)
        btn_container = tk.Frame(button_frame, bg=self.colors['light'])
        btn_container.pack()

        def proceed():
            room = self.room_choice.get()
            if not self.rooms:
                messagebox.showwarning("No Rooms", "No rooms available to select.")
                return
            if not room:
                messagebox.showwarning("Selection Required", "Please select a room type.")
                return
            if self.rooms[room]['available'] <= 0:
                messagebox.showerror("Unavailable", "Sorry, this room type is not available.")
                return
            selected_services = [s for s, v in self.service_vars.items() if v.get() == 1]
            nights_local = self.pending['nights']
            room_cost = self.rooms[room]['price'] * nights_local
            service_cost = sum(self.services[s] for s in selected_services) if selected_services else 0.0
            total = room_cost + service_cost
            self.pending['room'] = room
            self.pending['services'] = selected_services
            self.pending['total'] = total
            self.show_payment_method()

        self.create_hotelreservation_button(btn_container, "→ Proceed to Payment", proceed, 'success', 250)
        # Cancel Reservation goes to home
        self.create_hotelreservation_button(btn_container, "Cancel Reservation", lambda: self.confirm_cancel(), 'danger', 250)

    def _bind_preview_traces(self):
        # update preview when selections change
        try:
            if hasattr(self, 'room_choice') and isinstance(self.room_choice, tk.StringVar):
                try:
                    self.room_choice.trace_add('write', lambda *a: self._update_total_preview())
                except Exception:
                    self.room_choice.trace('w', lambda *a: self._update_total_preview())
        except Exception:
            pass
        for name, var in getattr(self, 'service_vars', {}).items():
            try:
                var.trace_add('write', lambda *a: self._update_total_preview())
            except Exception:
                try:
                    var.trace('w', lambda *a: self._update_total_preview())
                except Exception:
                    pass
        self._update_total_preview()

    def _update_total_preview(self):
        nights = self.pending.get('nights') or 1
        total = 0.0
        room_selected = getattr(self, 'room_choice', tk.StringVar()).get() if hasattr(self, 'room_choice') else ""
        if room_selected and room_selected in self.rooms:
            total += self.rooms[room_selected]['price'] * nights
        for s, var in getattr(self, 'service_vars', {}).items():
            if var.get() == 1:
                total += float(self.services.get(s, 0.0))
        if hasattr(self, 'total_preview_label'):
            self.total_preview_label.config(text=f"Total Preview: ₱{total:.2f}")

    def _on_test_db(self):
        conn, err = self.try_connect_silent()
        if conn:
            conn.close()
            self.rooms = self.load_rooms()
            self.services = self.load_services()
            messagebox.showinfo("DB Test", "Connected to database and loaded data. Refreshing room selection...")
            self.room_selection()
        else:
            messagebox.showerror("DB Test Failed", f"Could not connect to DB:\n{err}\n\nCheck credentials and that MySQL is running.")

    def _load_sample_data(self):
        self.rooms = {
            "Single Room": {"id": 1, "price": 1000.0, "available": 5},
            "Double Room": {"id": 2, "price": 1800.0, "available": 5},
            "Family Room": {"id": 3, "price": 3000.0, "available": 5},
        }
        self.services = {
            "Parking Space": 200.0,
            "Room Service": 500.0,
            "Shuttle Service": 800.0
        }
        messagebox.showinfo("Sample Data", "Sample rooms and services loaded (for testing).")
        self.room_selection()

    def show_payment_method(self):
        # Refresh local data in case it changed
        self.rooms = self.load_rooms()
        self.services = self.load_services()

        self.clear_window()
        main_frame = tk.Frame(self.root, bg=self.colors['light'])
        main_frame.pack(fill='both', expand=True)

        header_frame = tk.Frame(main_frame, bg=self.colors['secondary'], height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        tk.Label(header_frame, text="Payment Method", font=self.fonts['subheading'], bg=self.colors['secondary'], fg=self.colors['white']).pack(expand=True)

        content_frame = tk.Frame(main_frame, bg=self.colors['light'])
        content_frame.pack(fill='both', expand=True, padx=20, pady=20)

        payment_card, payment_content = self.create_card_frame(content_frame, "Payment Method")
        self.payment_choice = tk.StringVar(value="Cash")
        self.create_radio_group(payment_content, "Select Payment Method:", ["Cash", "Credit Card", "GCash", "Bank Transfer"], self.payment_choice)

        total_label = tk.Label(payment_content, text=f"Total to pay: ₱{self.pending.get('total', 0.0):.2f}", font=self.fonts['body_bold'], bg=self.colors['card'], fg=self.colors['dark_text'])
        total_label.pack(anchor='e', pady=(10,0))

        btn_frame = tk.Frame(content_frame, bg=self.colors['light'])
        btn_frame.pack(fill='x', pady=20)
        container = tk.Frame(btn_frame, bg=self.colors['light'])
        container.pack()

        def on_proceed():
            self.pending['payment'] = self.payment_choice.get()
            self.show_confirmation()

        self.create_hotelreservation_button(container, "Proceed", on_proceed, 'primary', 200)
        # Cancel Reservation goes to home
        self.create_hotelreservation_button(container, "Cancel Reservation", lambda: self.confirm_cancel(), 'danger', 200)

    def show_confirmation(self):
        self.clear_window()
        main_frame = tk.Frame(self.root, bg=self.colors['light'])
        main_frame.pack(fill='both', expand=True)

        header_frame = tk.Frame(main_frame, bg=self.colors['secondary'], height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        tk.Label(header_frame, text="Confirmation", font=self.fonts['subheading'], bg=self.colors['secondary'], fg=self.colors['white']).pack(expand=True)

        content_frame = tk.Frame(main_frame, bg=self.colors['light'])
        content_frame.pack(fill='both', expand=True, padx=20, pady=20)

        summary_card, summary_content = self.create_card_frame(content_frame, "Processing Reservation")
        tk.Label(summary_content, text="Please review and proceed.\nYou will be shown a final review screen.", font=self.fonts['body'], bg=self.colors['card'], fg=self.colors['dark_text']).pack(anchor='w')

        # Buttons: Cancel -> home, Proceed -> review
        btn_frame = tk.Frame(content_frame, bg=self.colors['light'])
        btn_frame.pack(fill='x', pady=20)
        container = tk.Frame(btn_frame, bg=self.colors['light'])
        container.pack()

        self.create_hotelreservation_button(container, "Cancel Reservation", lambda: self.confirm_cancel(), 'danger', 200)
        self.create_hotelreservation_button(container, "Proceed", lambda: self.show_review(), 'primary', 200)

    def show_review(self):
        self.clear_window()
        main_frame = tk.Frame(self.root, bg=self.colors['light'])
        main_frame.pack(fill='both', expand=True)

        header_frame = tk.Frame(main_frame, bg=self.colors['secondary'], height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        tk.Label(header_frame, text="Review Reservation", font=self.fonts['subheading'], bg=self.colors['secondary'], fg=self.colors['white']).pack(expand=True)

        content_frame = tk.Frame(main_frame, bg=self.colors['light'])
        content_frame.pack(fill='both', expand=True, padx=20, pady=20)

        review_card, review_content = self.create_card_frame(content_frame, "Reservation Summary")

        details = [
            ("Guest Name:", self.pending['name']),
            ("Phone Number:", self.pending['phone']),
            ("Room Type:", self.pending['room']),
            ("Number of Nights:", str(self.pending['nights'])),
            ("Services:", ', '.join(self.pending['services']) if self.pending['services'] else 'None'),
            ("Payment Method:", self.pending['payment']),
            ("", ""),
            ("Total Amount:", f"₱{self.pending['total']:.2f}")
        ]

        for label, value in details:
            if label == "":
                tk.Frame(review_content, height=2, bg=self.colors['border']).pack(fill='x', pady=10)
            else:
                row = tk.Frame(review_content, bg=self.colors['card'])
                row.pack(fill='x', pady=3)
                tk.Label(row, text=label, font=self.fonts['body_bold'], bg=self.colors['card'], fg=self.colors['dark_text']).pack(side='left')
                tk.Label(row, text=value, font=self.fonts['body'], bg=self.colors['card'], fg=self.colors['dark_text']).pack(side='right')

        btn_frame = tk.Frame(content_frame, bg=self.colors['light'])
        btn_frame.pack(pady=20)
        container = tk.Frame(btn_frame, bg=self.colors['light'])
        container.pack()

        # Cancel Reservation returns to home (with confirm)
        self.create_hotelreservation_button(container, "Cancel Reservation", lambda: self.confirm_cancel(), 'danger', 200)

        # Confirm finalizes reservation
        self.create_hotelreservation_button(container, "Confirm Reservation", self.finalize_reservation, 'success', 220)

    def finalize_reservation(self):
        # Save pending['payment'] should already be set
        name = self.pending['name']; phone = self.pending['phone']; nights = self.pending['nights']
        room = self.pending['room']; services = self.pending['services']; payment = self.pending['payment']; total = self.pending['total']

        # Final availability check
        if room not in self.rooms or self.rooms[room]['available'] <= 0:
            messagebox.showerror("Unavailable", "Sorry, this room type is no longer available.")
            self.room_selection()
            return

        if self.add_reservation(name, phone, room, nights, services, total, payment):
            # local cache already refreshed inside add_reservation
            # show receipt in toplevel
            self.generate_receipt(name, phone, room, nights, services, total, payment)
        else:
            messagebox.showerror("Error", "Failed to create reservation. Please try again.")
            self.room_selection()

    def generate_receipt(self, name, phone, room, nights, services, total, payment):
        receipt_window = tk.Toplevel(self.root)
        receipt_window.title("Reservation Confirmation")
        receipt_window.geometry("500x600")
        receipt_window.configure(bg=self.colors['light'])
        receipt_window.resizable(False, False)
        receipt_window.transient(self.root)
        receipt_window.grab_set()

        header_frame = tk.Frame(receipt_window, bg=self.colors['success'], height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        tk.Label(header_frame, text="✓ Reservation Confirmed!", font=self.fonts['subheading'], bg=self.colors['success'], fg=self.colors['white']).pack(expand=True)

        content_frame = tk.Frame(receipt_window, bg=self.colors['card'], padx=30, pady=20)
        content_frame.pack(fill='both', expand=True, padx=20, pady=20)

        details = [
            ("Guest Name:", name),
            ("Phone Number:", phone),
            ("Room Type:", room),
            ("Number of Nights:", str(nights)),
            ("Services:", ', '.join(services) if services else 'None'),
            ("Payment Method:", payment),
            ("", ""),
            ("Total Amount:", f"₱{total:.2f}")
        ]

        for label, value in details:
            if label == "":
                tk.Frame(content_frame, height=2, bg=self.colors['border']).pack(fill='x', pady=10)
            else:
                row = tk.Frame(content_frame, bg=self.colors['card'])
                row.pack(fill='x', pady=3)
                tk.Label(row, text=label, font=self.fonts['body_bold'], bg=self.colors['card'], fg=self.colors['dark_text']).pack(side='left')
                tk.Label(row, text=value, font=self.fonts['body'], bg=self.colors['card'], fg=self.colors['dark_text']).pack(side='right')

        def on_close_receipt():
            try:
                receipt_window.destroy()
            except Exception:
                pass
            # return user to welcome screen and reset pending
            self.reset_pending()
            self.show_welcome()

        self.create_hotelreservation_button(content_frame, "✓ Close", on_close_receipt, 'primary', 150)

    # ---------- Staff view ----------
    def view_reservations(self):
        # ensure local cache up-to-date
        self.rooms = self.load_rooms()
        self.services = self.load_services()

        rows = self.get_reservations()
        # always create a Toplevel so staff can keep main window open
        view_window = tk.Toplevel(self.root)
        view_window.title("Reservation Management - LitHo Hotel")
        view_window.geometry("1200x700")
        view_window.configure(bg=self.colors['light'])

        header_frame = tk.Frame(view_window, bg=self.colors['primary'], height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        tk.Label(header_frame, text="Reservation Management", font=self.fonts['subheading'], bg=self.colors['primary'], fg=self.colors['white']).pack(expand=True)

        content_frame = tk.Frame(view_window, bg=self.colors['light'])
        content_frame.pack(fill='both', expand=True, padx=20, pady=20)

        tree_frame = tk.Frame(content_frame, bg=self.colors['card'])
        tree_frame.pack(fill='both', expand=True)

        v_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical')
        h_scrollbar = ttk.Scrollbar(tree_frame, orient='horizontal')

        tree = ttk.Treeview(tree_frame, columns=('ID', 'Guest Name', 'Phone', 'Room', 'Nights', 'Services', 'Total', 'Payment'), show='headings', yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        v_scrollbar.configure(command=tree.yview)
        h_scrollbar.configure(command=tree.xview)
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')
        tree.pack(fill='both', expand=True)

        column_widths = [60, 150, 120, 120, 80, 150, 100, 120]
        cols = ('ID', 'Guest Name', 'Phone', 'Room', 'Nights', 'Services', 'Total', 'Payment')
        for col, w in zip(cols, column_widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, minwidth=w)

        if not rows:
            # show informative label
            info_label = tk.Label(tree_frame, text="No reservations found.", bg=self.colors['card'], fg=self.colors['dark_text'], font=self.fonts['body'])
            info_label.place(relx=0.5, rely=0.5, anchor='center')
        else:
            for row in rows:
                try:
                    res_id, name, phone, room, nights, services, total, payment = row
                    display_total = f"₱{total}"
                except Exception:
                    vals = tuple(row)
                    vals = tuple(list(vals)[:8] + [""] * (8 - len(vals)))
                    res_id, name, phone, room, nights, services, total, payment = vals
                    display_total = f"₱{total}" if total != "" else ""
                tree.insert('', 'end', values=(res_id, name, phone, room, nights, services, display_total, payment))

        # Buttons at bottom of the Toplevel
        button_frame = tk.Frame(content_frame, bg=self.colors['light'])
        button_frame.pack(fill='x', pady=20)
        container = tk.Frame(button_frame, bg=self.colors['light'])
        container.pack()

        def refresh_tree():
            # clear, reload rows and repopulate
            for i in tree.get_children():
                tree.delete(i)
            new_rows = self.get_reservations()
            for row in new_rows:
                try:
                    res_id, name, phone, room, nights, services, total, payment = row
                    display_total = f"₱{total}"
                except Exception:
                    vals = tuple(row)
                    vals = tuple(list(vals)[:8] + [""] * (8 - len(vals)))
                    res_id, name, phone, room, nights, services, total, payment = vals
                    display_total = f"₱{total}" if total != "" else ""
                tree.insert('', 'end', values=(res_id, name, phone, room, nights, services, display_total, payment))

        def remove_selected():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("Selection Required", "Please select a reservation to remove.")
                return
            item = selected[0]
            values = tree.item(item, 'values')
            res_id = values[0]
            guest_name = values[1]
            if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to remove the reservation for {guest_name}?\n\nThis action cannot be undone."):
                if self.delete_reservation(res_id):
                    messagebox.showinfo("Success", "Reservation removed successfully.")
                    # refresh local tree and caches
                    refresh_tree()
                else:
                    messagebox.showerror("Error", "Failed to remove reservation. Please try again.")

        tk.Button(container, text="🗑️ Remove Selected", command=remove_selected, bg=self.colors['accent'], fg=self.colors['white'], relief='flat', padx=20, pady=10).pack(side='left', padx=10)
        # Cancel Reservation on the Toplevel: confirm then close to home
        tk.Button(container, text="Cancel Reservation", command=lambda: self.confirm_cancel(current_toplevel=view_window), bg=self.colors['accent'], fg=self.colors['white'], relief='flat', padx=20, pady=10).pack(side='left', padx=10)

# ---------- Run the application ----------
if __name__ == "__main__":
    root = tk.Tk()
    app = HotelReservation(root)
    root.mainloop()
