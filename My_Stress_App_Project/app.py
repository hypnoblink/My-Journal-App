import customtkinter as ctk
import mysql.connector
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from tkinter import messagebox, simpledialog
from plyer import notification 
import threading
import time
import pygame 
import os  
import bcrypt  # Secure password hashing

# --- DATABASE CONNECTION ---
def get_db():
    try:
        return mysql.connector.connect(
            host="localhost", user="root", password="", 
            database="journal_system", port=3307 
        )
    except Exception as e:
        print(f"[Database Error] Connection failed: {e}")
        return None

# ==============================================================================
# LOGIN & SIGN-UP FRAME
# ==============================================================================
class AuthFrame(ctk.CTkFrame):
    def __init__(self, parent, theme_config, on_auth_success):
        super().__init__(parent, fg_color="transparent")
        self.parent = parent
        self.theme_config = theme_config
        self.on_auth_success = on_auth_success
        self.is_login_mode = True
        
        self.pack(fill="both", expand=True)
        self.render_auth_ui()

    def render_auth_ui(self):
        # Clear frame if switching states
        for widget in self.winfo_children():
            widget.destroy()

        cur_theme = self.theme_config["dark"] if self.parent.is_dark else self.theme_config["light"]
        
        # Centered Container Card
        self.card = ctk.CTkFrame(self, width=420, height=520, fg_color=cur_theme["card"], corner_radius=20)
        self.card.place(relx=0.5, rely=0.5, anchor="center")
        self.card.pack_propagate(False)

        # Title
        title_text = "Welcome Back" if self.is_login_mode else "Create Account"
        self.lbl_title = ctk.CTkLabel(self.card, text=title_text, font=("Arial", 26, "bold"), text_color=cur_theme["text"])
        self.lbl_title.pack(pady=(40, 30))

        # Username Input
        self.lbl_user = ctk.CTkLabel(self.card, text="Username", font=("Arial", 12, "bold"), text_color="#7d8597")
        self.lbl_user.pack(padx=40, anchor="w")
        self.username_input = ctk.CTkEntry(self.card, height=40, fg_color=cur_theme["input"], text_color=cur_theme["text"])
        self.username_input.pack(pady=(5, 15), padx=40, fill="x")

        # Password Input
        self.lbl_pass = ctk.CTkLabel(self.card, text="Password", font=("Arial", 12, "bold"), text_color="#7d8597")
        self.lbl_pass.pack(padx=40, anchor="w")
        self.password_input = ctk.CTkEntry(self.card, height=40, show="•", fg_color=cur_theme["input"], text_color=cur_theme["text"])
        self.password_input.pack(pady=(5, 25), padx=40, fill="x")

        # Action Button
        btn_text = "Login" if self.is_login_mode else "Register Account"
        self.action_btn = ctk.CTkButton(self.card, text=btn_text, height=45, font=("Arial", 15, "bold"),
                                        fg_color=self.theme_config["accent"], hover_color=self.theme_config["hover"],
                                        command=self.handle_auth)
        self.action_btn.pack(padx=40, fill="x", pady=5)

        # Switch Link
        link_text = "Don't have an account? Sign up" if self.is_login_mode else "Already have an account? Log in"
        self.switch_btn = ctk.CTkButton(self.card, text=link_text, font=("Arial", 12, "underline"),
                                        fg_color="transparent", text_color=self.theme_config["accent"],
                                        hover_color=cur_theme["card"], command=self.toggle_mode)
        self.switch_btn.pack(pady=15)

    def toggle_mode(self):
        self.parent.play_sfx("click")
        self.is_login_mode = not self.is_login_mode
        self.render_auth_ui()

    def handle_auth(self):
        username = self.username_input.get().strip()
        password = self.password_input.get().strip()

        if not username or not password:
            messagebox.showwarning("Incomplete Fields", "Please populate both username and password entry ports.")
            return

        db = get_db()
        if not db:
            messagebox.showerror("Database Offline", "Could not establish database sync. Verify XAMPP settings.")
            return

        cursor = db.cursor()

        if self.is_login_mode:
            # LOGIN ROUTINE
            cursor.execute("SELECT user_id, password_hash FROM users WHERE username = %s", (username,))
            user_record = cursor.fetchone()
            
            if user_record and bcrypt.checkpw(password.encode('utf-8'), user_record[1].encode('utf-8')):
                self.parent.play_sfx("success")
                current_user_id = user_record[0]
                db.close()
                self.destroy()
                self.on_auth_success(current_user_id, username)
            else:
                messagebox.showerror("Authentication Failed", "Invalid username or password match found.")
                db.close()
        else:
            # SIGN-UP ROUTINE
            try:
                cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
                if cursor.fetchone():
                    messagebox.showwarning("Unavailable", "Username already exists. Please choose another.")
                    db.close()
                    return

                # Hash password securely
                hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, hashed))
                db.commit()
                
                self.parent.play_sfx("success")
                messagebox.showinfo("Success", "Account registered successfully! Please log in now.")
                db.close()
                self.is_login_mode = True
                self.render_auth_ui()
            except Exception as e:
                messagebox.showerror("System Error", f"Registration profile insertion failure: {e}")
                db.close()


# ==============================================================================
# MAIN APPLICATION ENGINE
# ==============================================================================
class GlassJournalApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- CENTRALIZED THEME CONFIGURATION ---
        self.theme_config = {
            "dark": {"bg": "#1a1c24", "card": "#252936", "text": "#ffffff", "input": "#1a1c24"},
            "light": {"bg": "#f0f2f5", "card": "#ffffff", "text": "#333333", "input": "#ffffff"},
            "accent": "#3b82f6",
            "hover": "#60a5fa",
            "delete": "#ef4444",
            "delete_hover": "#dc2626"
        }

        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.mixer.init()
        except Exception as e:
            print(f"[Audio Error] Failed to initialize pygame mixer: {e}")

        self.sounds = {}
        self.load_sounds()

        self.title("Self Reflective Journal")
        self.geometry("1300x900") 
        
        self.is_dark = True
        ctk.set_appearance_mode("dark")
        self.chart_view = "Daily" 
        self.reminder_active = False
        
        # User session tracking variables
        self.current_user_id = None
        self.current_username = None

        # Load Authentication flow first
        self.auth_screen = AuthFrame(self, self.theme_config, self.login_success_callback)

    def login_success_callback(self, user_id, username):
        self.current_user_id = user_id
        self.current_username = username
        self.initialize_main_interface()

    def initialize_main_interface(self):
        # Fetch user configurations from database
        db = get_db()
        if db:
            cursor = db.cursor()
            cursor.execute("SELECT theme_mode, reminder_time FROM settings WHERE user_id = %s", (self.current_user_id,))
            setting = cursor.fetchone()
            
            if setting:
                self.is_dark = (setting[0] == "Dark")
                self.saved_reminder_time = str(setting[1]) # e.g., "08:00:00"
            else:
                # Fallback if user doesn't have a settings row yet
                self.is_dark = True
                self.saved_reminder_time = "20:00:00"
                cursor.execute("INSERT INTO settings (user_id, theme_mode, reminder_time) VALUES (%s, 'Dark', '18:00:00')", (self.current_user_id,))
                db.commit()
            db.close()

        ctk.set_appearance_mode("dark" if self.is_dark else "light")
        
        # --- TAB NAVIGATION ---
        self.tabs = ctk.CTkTabview(self, segmented_button_selected_color=self.theme_config["accent"])
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(10, 20)) 
            
        self.tab_dashboard = self.tabs.add("Dashboard")
        self.tab_history = self.tabs.add("Journal History")

        cur_card = self.theme_config["dark"]["card"] if self.is_dark else self.theme_config["light"]["card"]
            
        # Dynamic Settings/User Button Layout
        self.settings_btn = ctk.CTkButton(self, text=f"⚙ {self.current_username}", width=130, height=35,
                                              fg_color=cur_card, 
                                              hover_color=self.theme_config["hover"],
                                              command=self.toggle_settings_panel)
        self.settings_btn.place(relx=0.86, rely=0.015)

        self.render_dashboard()
        self.render_history_tab()

    def load_sounds(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        sound_files = {"click": "click.wav", "success": "success.wav", "toggle": "toggle.wav"}
        
        for name, filename in sound_files.items():
            full_path = os.path.join(base_dir, filename)
            if not os.path.exists(full_path):
                print(f"[Audio Warning] File not found: {full_path}")
                self.sounds[name] = None
                continue
            try:
                self.sounds[name] = pygame.mixer.Sound(full_path)
                self.sounds[name].set_volume(0.3) 
            except Exception as e:
                print(f"[Audio Error] Could not load sound '{name}': {e}")
                self.sounds[name] = None

    def play_sfx(self, sound_name):
        sound = self.sounds.get(sound_name)
        if sound: 
            sound.play()

    def render_dashboard(self):
        self.tab_dashboard.grid_columnconfigure(0, weight=70) 
        self.tab_dashboard.grid_columnconfigure(1, weight=25)
        self.tab_dashboard.grid_rowconfigure(0, weight=1)

        cur_theme = self.theme_config["dark"] if self.is_dark else self.theme_config["light"]

        self.left_panel = ctk.CTkScrollableFrame(self.tab_dashboard, fg_color=cur_theme["card"], corner_radius=20)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 15), pady=10)

        self.lbl_title = ctk.CTkLabel(self.left_panel, text=f"Hello, {self.current_username}", font=("Arial", 28, "bold"), text_color=cur_theme["text"])
        self.lbl_title.pack(pady=(15, 5), padx=35, anchor="w")
        
        self.lbl_subtitle = ctk.CTkLabel(self.left_panel, text="Log a New Entry", font=("Arial", 14), text_color="#7d8597")
        self.lbl_subtitle.pack(pady=(0, 10), padx=35, anchor="w")
        
        self.category_dropdown = ctk.CTkOptionMenu(self.left_panel, values=["Academics", "Personal Health", "Relationships"], 
                                                   fg_color=self.theme_config["accent"], height=38, font=("Arial", 14))
        self.category_dropdown.pack(pady=5, padx=35, fill="x")

        self.lbl_stress_tag = ctk.CTkLabel(self.left_panel, text="Stress Level (1-10)", font=("Arial", 14), text_color=cur_theme["text"])
        self.lbl_stress_tag.pack(padx=35, anchor="w", pady=(10, 0))
        
        self.stress_slider = ctk.CTkSlider(self.left_panel, from_=1, to=10, number_of_steps=9)
        self.stress_slider.pack(pady=10, padx=35, fill="x")

        self.lbl_journal_entry = ctk.CTkLabel(self.left_panel, text="Journal Text", font=("Arial", 16, "bold"), text_color=cur_theme["text"])
        self.lbl_journal_entry.pack(padx=35, anchor="w", pady=(10, 5))

        self.journal_input = ctk.CTkTextbox(self.left_panel, height=300, font=("Arial", 14), fg_color=cur_theme["input"], text_color=cur_theme["text"])
        self.journal_input.pack(pady=(0, 5), padx=35, fill="x")
        self.journal_input.bind("<KeyRelease>", self.update_char_count)

        self.lbl_char_count = ctk.CTkLabel(self.left_panel, text="Characters: 0", font=("Arial", 11), text_color="#7d8597")
        self.lbl_char_count.pack(padx=40, anchor="e")

        self.submit_btn = ctk.CTkButton(self.left_panel, text="Save to Journal", 
                                        font=("Arial", 16, "bold"), height=45,
                                        fg_color=self.theme_config["accent"], hover_color=self.theme_config["hover"],
                                        command=self.save_to_db)
        self.submit_btn.pack(pady=5, padx=35, fill="x")

        self.graph_frame = ctk.CTkFrame(self.tab_dashboard, fg_color="transparent")
        self.graph_frame.grid(row=0, column=1, sticky="nsew", pady=10)
        self.graph_frame.grid_rowconfigure(0, weight=1)
        self.graph_frame.grid_rowconfigure(1, weight=1)

        self.refresh_charts()

    def update_char_count(self, event=None):
        count = len(self.journal_input.get("1.0", "end-1c"))
        self.lbl_char_count.configure(text=f"Characters: {count}")

    def render_history_tab(self):
        cur_theme = self.theme_config["dark"] if self.is_dark else self.theme_config["light"]
        self.history_title = ctk.CTkLabel(self.tab_history, text="Journal History", font=("Arial", 28, "bold"), text_color=cur_theme["text"])
        self.history_title.pack(pady=20, padx=35, anchor="w")
        
        self.history_list = ctk.CTkScrollableFrame(self.tab_history, fg_color=cur_theme["card"], corner_radius=20)
        self.history_list.pack(fill="both", expand=True, padx=35, pady=(0, 20))
        
        self.load_history()

    def load_history(self):
        for widget in self.history_list.winfo_children():
            widget.destroy()

        db = get_db()
        cur_theme = self.theme_config["dark"] if self.is_dark else self.theme_config["light"]
        
        if db:
            cursor = db.cursor()
            cursor.execute("""
                SELECT e.entry_id, e.journal_text, e.stress_level, e.created_at, c.category_name 
                FROM entries e 
                JOIN categories c ON e.category_id = c.category_id 
                WHERE e.user_id = %s
                ORDER BY e.created_at DESC
            """, (self.current_user_id,))
            rows = cursor.fetchall()

            if not rows:
                ctk.CTkLabel(self.history_list, text="No entries yet. Start your journey by writing on the Dashboard!", 
                             font=("Arial", 16, "italic"), text_color="#7d8597").pack(pady=60)
                db.close()
                return

            for (eid, text, stress, date, cat) in rows:
                item = ctk.CTkFrame(self.history_list, fg_color=cur_theme["input"], corner_radius=12)
                item.pack(fill="x", pady=10, padx=15)
                
                header = f"{date.strftime('%B %d, %Y')} | {cat} | Stress: {stress}/10"
                ctk.CTkLabel(item, text=header, font=("Arial", 13, "bold"), text_color=self.theme_config["accent"]).pack(anchor="w", padx=20, pady=(15, 0))
                
                ctk.CTkLabel(item, text=text, font=("Arial", 14), wraplength=800, justify="left", text_color=cur_theme["text"]).pack(anchor="w", padx=20, pady=12)

                btn_frame = ctk.CTkFrame(item, fg_color="transparent")
                btn_frame.pack(anchor="e", padx=15, pady=(0, 15))

                ctk.CTkButton(btn_frame, text="Edit", width=70, height=30, 
                             hover_color=self.theme_config["hover"],
                             command=lambda i=eid, t=text: self.edit_entry(i, t)).pack(side="left", padx=5)
                ctk.CTkButton(btn_frame, text="Delete", width=70, height=30, 
                             fg_color=self.theme_config["delete"], 
                             hover_color=self.theme_config["delete_hover"], 
                             command=lambda i=eid: self.delete_entry(i)).pack(side="left", padx=5)
            db.close()

    def save_to_db(self):
        content = self.journal_input.get("1.0", "end-1c")
        if not content.strip():
            messagebox.showwarning("Empty", "Please write something first!")
            return
        
        db = get_db()
        if db:
            cursor = db.cursor()
            cursor.execute("SELECT category_id FROM categories WHERE category_name = %s", (self.category_dropdown.get(),))
            res = cursor.fetchone()
            if res:
                cursor.execute("INSERT INTO entries (user_id, category_id, stress_level, journal_text) VALUES (%s, %s, %s, %s)", 
                               (self.current_user_id, res[0], int(self.stress_slider.get()), content))
                db.commit()
                self.play_sfx("success")
                messagebox.showinfo("Success", "Journal saved!")
                self.journal_input.delete("1.0", "end")
                self.update_char_count()
                self.load_history()
                self.refresh_charts()
            db.close()

    def change_theme(self):
        self.is_dark = self.theme_switch.get()
        theme_str = "Dark" if self.is_dark else "Light"
        ctk.set_appearance_mode("dark" if self.is_dark else "light")
        
        cur_theme = self.theme_config["dark"] if self.is_dark else self.theme_config["light"]
        
        self.configure(fg_color=cur_theme["bg"])
        self.left_panel.configure(fg_color=cur_theme["card"])
        self.history_list.configure(fg_color=cur_theme["card"])
        self.settings_btn.configure(fg_color=cur_theme["card"])
        
        self.lbl_title.configure(text_color=cur_theme["text"])
        self.lbl_stress_tag.configure(text_color=cur_theme["text"])
        self.lbl_journal_entry.configure(text_color=cur_theme["text"])
        self.history_title.configure(text_color=cur_theme["text"])
        
        self.journal_input.configure(fg_color=cur_theme["input"], text_color=cur_theme["text"])
        self.refresh_charts()
        self.load_history()

        db = get_db()
        if db:
            cursor = db.cursor()
            cursor.execute("UPDATE settings SET theme_mode = %s WHERE user_id = %s", (theme_str, self.current_user_id))
            db.commit()
            db.close()

    def delete_entry(self, entry_id):
        if messagebox.askyesno("Confirm", "Delete this entry?"):
            db = get_db()
            if db:
                cursor = db.cursor()
                cursor.execute("DELETE FROM entries WHERE entry_id = %s", (entry_id,))
                db.commit()
                db.close()
                self.load_history()
                self.refresh_charts()

    def edit_entry(self, entry_id, old_text):
        new_text = simpledialog.askstring("Edit", "Modify your entry:", initialvalue=old_text)
        if new_text:
            db = get_db()
            if db:
                cursor = db.cursor()
                cursor.execute("UPDATE entries SET journal_text = %s WHERE entry_id = %s", (new_text, entry_id))
                db.commit()
                db.close()
                self.load_history()

    def refresh_charts(self):
        for widget in self.graph_frame.winfo_children():
            widget.destroy()

        db = get_db()
        line_data, bar_data = {'labels': [], 'levels': []}, {'categories': [], 'counts': []}
        cur_theme = self.theme_config["dark"] if self.is_dark else self.theme_config["light"]

        if db:
            cursor = db.cursor()
            if self.chart_view == "Daily":
                cursor.execute("""
                    SELECT DATE_FORMAT(created_at, '%b %d'), AVG(stress_level) 
                    FROM entries WHERE user_id = %s GROUP BY DATE(created_at) ORDER BY created_at ASC LIMIT 7
                """, (self.current_user_id,))
            else:
                cursor.execute("""
                    SELECT CONCAT('Wk ', WEEK(created_at)), AVG(stress_level) 
                    FROM entries WHERE user_id = %s GROUP BY WEEK(created_at) ORDER BY created_at ASC
                """, (self.current_user_id,))
            
            rows = cursor.fetchall()
            line_data['labels'] = [r[0] for r in rows]
            line_data['levels'] = [float(r[1]) for r in rows]

            cursor.execute("""
                SELECT c.category_name, COUNT(e.entry_id) 
                FROM categories c 
                LEFT JOIN entries e ON c.category_id = e.category_id AND e.user_id = %s 
                GROUP BY c.category_name
            """, (self.current_user_id,))
            rows = cursor.fetchall()
            bar_data['categories'] = [r[0] for r in rows]
            bar_data['counts'] = [r[1] for r in rows]
            db.close()

        trend_card = ctk.CTkFrame(self.graph_frame, fg_color=cur_theme["card"], corner_radius=20)
        trend_card.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        
        self.toggle_btn = ctk.CTkButton(trend_card, text=f"Show { 'Weekly' if self.chart_view == 'Daily' else 'Daily' }", 
                                        width=110, height=28, font=("Arial", 11, "bold"),
                                        command=self.toggle_chart_view)
        self.toggle_btn.pack(anchor="ne", padx=20, pady=10)
        self.plot_chart(trend_card, line_data, "line")

        trigger_card = ctk.CTkFrame(self.graph_frame, fg_color=cur_theme["card"], corner_radius=20)
        trigger_card.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        self.plot_chart(trigger_card, bar_data, "bar")

    def toggle_chart_view(self):
        self.play_sfx("click")
        self.chart_view = "Weekly" if self.chart_view == "Daily" else "Daily"
        self.refresh_charts()

    def plot_chart(self, parent, data, type):
        cur_theme = self.theme_config["dark"] if self.is_dark else self.theme_config["light"]

        fig, ax = plt.subplots(figsize=(5, 3.0), facecolor=cur_theme["card"]) 
        ax.set_facecolor(cur_theme["card"])
        ax.tick_params(colors="#7d8597", labelsize=9)
        for s in ax.spines.values(): s.set_visible(False)
        
        if type == "line":
            ax.set_title(f"Stress Trends ({self.chart_view})", color=cur_theme["text"], fontsize=12, fontweight="bold")
            if data['labels']: ax.plot(data['labels'], data['levels'], color=self.theme_config["accent"], marker='o', linewidth=2.5)
        else:
            ax.set_title("Entries by Category", color=cur_theme["text"], fontsize=12, fontweight="bold")
            ax.barh(data['categories'], data['counts'], color='#60a5fa')
            plt.subplots_adjust(left=0.3)

        plt.tight_layout()
        FigureCanvasTkAgg(fig, master=parent).get_tk_widget().pack(fill="both", expand=True, padx=15, pady=5)

    def toggle_settings_panel(self):
        self.play_sfx("click")
        if hasattr(self, 'settings_panel') and self.settings_panel.winfo_exists():
            self.update_idletasks()
            self.settings_panel.destroy()
            return
        
        cur_theme = self.theme_config["dark"] if self.is_dark else self.theme_config["light"]
        border_col = "#3a3f50" if self.is_dark else "#d1d5db"
        
        self.settings_panel = ctk.CTkFrame(self, width=280, height=420, 
                                           fg_color=cur_theme["card"], 
                                           border_width=2, border_color=border_col)
        self.settings_panel.place(relx=0.78, rely=0.07)
        
        ctk.CTkLabel(self.settings_panel, text="Settings", font=("Arial", 18, "bold"), text_color=cur_theme["text"]).pack(pady=15)
        
        self.theme_switch = ctk.CTkSwitch(self.settings_panel, text="Dark Mode", command=self.change_theme, text_color=cur_theme["text"])
        if self.is_dark: self.theme_switch.select()
        self.theme_switch.pack(pady=10, padx=25, anchor="w")

        ctk.CTkLabel(self.settings_panel, text="Reminder Time (e.g., 08:30 PM)", font=("Arial", 12), text_color=cur_theme["text"]).pack(padx=25, anchor="w")
        self.time_entry = ctk.CTkEntry(self.settings_panel, width=170)
        self.time_entry.insert(0, "08:00 PM")
        self.time_entry.pack(pady=5, padx=25, anchor="w")

        self.notif_switch = ctk.CTkSwitch(self.settings_panel, text="Enable Notification", command=self.toggle_reminder, text_color=cur_theme["text"])
        self.notif_switch.pack(pady=10, padx=25, anchor="w")

        # Added Logout option inside the settings view
        self.logout_btn = ctk.CTkButton(self.settings_panel, text="Logout Session", 
                                        fg_color=self.theme_config["delete"], hover_color=self.theme_config["delete_hover"],
                                        command=self.handle_logout)
        self.logout_btn.pack(pady=20, padx=25, fill="x")

    def handle_logout(self):
        self.play_sfx("click")
        if messagebox.askyesno("Confirm Logout", "Are you sure you want to log out?"):
            self.settings_panel.destroy()
            self.tabs.destroy()
            self.settings_btn.destroy()
            
            self.current_user_id = None
            self.current_username = None
            
            # Restart system state back into landing screen
            self.auth_screen = AuthFrame(self, self.theme_config, self.login_success_callback)

    def toggle_reminder(self):
        self.play_sfx("toggle")
        self.reminder_active = (self.notif_switch.get() == 1)
        if self.reminder_active:
            target = self.time_entry.get().strip()
            threading.Thread(target=self.reminder_loop, args=(target,), daemon=True).start()

    def reminder_loop(self, target):
        while self.reminder_active:
            current_time = time.strftime("%I:%M %p") 
            if current_time.lower() == target.lower():
                try:
                    notification.notify(
                        title="Journal Reminder", 
                        message="Time for your self-reflection! 📝",
                        app_name="GlassJournal"
                    )
                except Exception as e:
                    print(f"[Notification Error] {e}")
                time.sleep(61) 
            time.sleep(5)

if __name__ == "__main__":
    app = GlassJournalApp()
    app.mainloop()