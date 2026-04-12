# FritzCall – Enigma2 Plugin

Incoming call notification and call history plugin for Enigma2. Displays
caller name/number (resolved from the Fritz!Box phonebook) on the TV screen
and/or the receiver's LCD display. Requires an AVM Fritz!Box router.

---

## Features

| Button | Action |
|--------|--------|
| **Red** | Close / Back |
| **Green** | Refresh call list |
| **Yellow** | Open Information screen |
| **Blue** | Open Settings |
| **OK** | View call details |
| **Left / Right** | Switch call filter (All / Missed / Answered / Outgoing) |

### Incoming call notifications
When a call comes in the Fritz!Box sends an event via the call monitor port
(1012). FritzCall displays a pop-up with caller name (resolved from the
Fritz!Box phonebook) and number on the TV screen.

---

## Requirements

- AVM Fritz!Box with call monitor enabled (`#96*5*` on any connected phone)
- Fritz!Box user account with phonebook read access

---

## Build & deploy

```bash
# 1. Copy .env.example to .env and enter your box credentials
cp .env.example .env

# 2. Build the .ipk package
make build

# 3. Build, upload and install on the box
make install

# 4. Restart Enigma2
make restart

# 5. Or do all three steps at once
make deploy
```

The package is placed in `build/enigma2-plugin-extensions-fritzcall_1.0.0_all.ipk`.

---

## Settings

| Setting | Description |
|---------|-------------|
| Fritz!Box host | Hostname or IP (default: `fritz.box`) |
| Fritz!Box user | Fritz!Box user with phonebook access |
| Fritz!Box password | Account password |
| LCD notification | Show caller on LCD display (if available) |
| Popup timeout | How long the incoming call notification stays visible |

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

Found a bug or have a suggestion for improvement? Please create an issue or pull request.

I appreciate everyone who supports me and the project! For any requests and suggestions, feel free to provide feedback.

<p>
  <a href="https://www.buymeacoffee.com/madoe21">
    <img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" height="50" alt="Buy Me a Coffee">
  </a>

  <a href="https://ko-fi.com/madoe21">
    <img src="https://storage.ko-fi.com/cdn/kofi3.png?v=3" height="50" alt="Ko-fi">
  </a>

  <a href="https://paypal.me/MartinD809">
    <img src="https://www.paypalobjects.com/webstatic/mktg/logo/pp_cc_mark_111x69.jpg" height="50" alt="PayPal">
  </a>
</p>
