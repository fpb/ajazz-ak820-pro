# AJAZZ AK820PRO reverse engineering

This is just a way to document my findings regarding the board of my AJAZZ AK820PRO (BT/USB/2.4G 81 keys)

## TODO List - Perhaps some kind souls will add QMK support for it
- [ ] map lcd module connections
- [ ] map indicators led (Caps lock, Win lock)
- [ ] check connections

## Chips
* Main MCU - HFD80CP100 - appears to be based on/clone of [SONIX SN32F99](https://www.sonix.com.tw/article-jp-4797-39755)
![mcu-hfd](./img/mcu-hfd80cp100.jpg)

* Bt module [WCH CH582F](https://www.wch-ic.com/products/CH583.html?)
  ![ak820-bt](./img/ak820pro-bt.jpg)

* External 16MB flash module [PY25Q128HA](https://puyasemi.com/uploadfiles/2022/09/20220913130446446.pdf)![ak820pro-flash](./img/ak820pro-flash.jpg)

* LCD Module - 0.85" 128x128 [NFP085B-10AF](https://cdn.hackaday.io/files/1881838051221472/GC9107%20DataSheet%20V1.2.pdf)

## Key Matrix & MCU
[Keyboard Layout](http://www.keyboard-layout-editor.com/##@@_c=%2393acb8&t=%23ffffff&a:6%3B&=Esc&_x:0.25&c=%23cccccc&t=%239989b3%3B&=F1&=F2&=F3&=F4&_x:0.25&c=%239989b3&t=%23cccccc%3B&=F5&=F6&=F7&=F8&_x:0.25&c=%23cccccc&t=%239989b3%3B&=F9&=F10&=F11&=F12&_x:0.25&c=%239989b3&t=%23cccccc%3B&=Delete%3B&@_y:0.25&c=%23cccccc&t=%239989b3&a:4&fa@:4&:4%3B%3B&=~%0A%60&=!%0A1&=%2F@%0A2&=%23%0A3&=$%0A4&=%25%0A5&=%5E%0A6&=%2F&%0A7&=*%0A8&=(%0A9&=)%0A0&=%2F_%0A-&=+%0A%2F=&_c=%239989b3&t=%23cccccc&a:6&f2=undefined&w:2%3B&=%3C-%20Backspace&_x:0.5%3B&=Home%3B&@_a:4&w:1.5%3B&=%3C-%0A-%3E%0A%0A%0A%0A%0ATab&_c=%23cccccc&t=%239989b3&fa@:6%3B%3B&=Q&=W&=E&=R&=T&=Y&=U&=I&=O&=P&_fa@:4&:4%3B%3B&=%7B%0A%5B&=%7D%0A%5D&_w:1.5%3B&=%7C%0A%5C&_x:0.5&c=%239989b3&t=%23cccccc&a:6&f:3%3B&=PgUp%3B&@_f:3&w:1.75%3B&=Caps%20Lock&_c=%23cccccc&t=%239989b3&a:4&fa@:6&:4&:0&:0&:0&:0&:0&:0&:0&:0%3B%3B&=A&=S&=D&_n:true%3B&=F&=G&=H&_n:true%3B&=J&=K&=L&_fa@:4&:4%3B%3B&=%2F:%0A%2F%3B&=%22%0A'&_c=%2393acb8&t=%23cccccc&a:6&f:3&w:2.25%3B&=Enter&_x:0.5&c=%239989b3&f:3%3B&=PgDn%3B&@_f:3&w:2.25%3B&=Shift&_c=%23cccccc&t=%239989b3&a:4&fa@:6%3B%3B&=Z&=X&=C&=V&=B&=N&=M&_fa@:4&:4%3B%3B&=%3C%0A,&=%3E%0A.&=%3F%0A%2F%2F&_c=%239989b3&t=%23cccccc&a:6&f:3&w:1.75%3B&=Shift%3B&@_y:-0.75&x:14.25&a:4&fa@:9%3B%3B&=↑%3B&@_y:-0.25&a:6&f:3&w:1.25%3B&=Ctrl&_f:3&w:1.25%3B&=Win&_f:3&w:1.25%3B&=Alt&_c=%2393acb8&a:7&w:6.25%3B&=&_c=%239989b3&a:6&f:3%3B&=Alt&_f:3%3B&=Fn&_f:3%3B&=Ctrl%3B&@_y:-0.75&x:13.25&a:4%3B&=←&=↓&=→)
<img width="912" alt="image" src="https://github.com/fpb/ajazz-820-pro/assets/456959/47b6e33f-249f-44f9-92f7-060f192f8aa1">

![Keyboard-layout](./img/ak820pro-layout.png)

![Key-Matrix](./img/ak820pro-wiring.png)

## MCU-Diagram - Keyboard matrix diagram on trhe MCU

| --- | col | C0 | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | C9 | C10 | C11 | C12 | C13 | C14 | C15 | C16 | C17 | C18 |
| --- | --- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| row | pin | 25 | 26 | 27 | 28 | 29 | 30 | 31 | 32 | 34 | 35 | 36  | 37  | 38  | 39  | 40  | 41  | 42  | 43  | 44  |
| R0  | 64  |    |    |    |    |    |    |    |    |    |    |     |     |     |     |     |     |     |     |     |
| R1  | 63  |    |    |    |    |    |    |    |    |    |    |     |     |     |     |     |     |     |     |     |
| R2  | 62  |    |    |    |    |    |    |    |    |    |    |     |     |     |     |     |     |     |     |     |
| R3  | 61  |    |    |    |    |    |    |    |    |    |    |     |     |     |     |     |     |     |     |     |
| R4  | 60  |    |    |    |    |    |    |    |    |    |    |     |     |     |     |     |     |     |     |     |
| R5  | 59  |    |    |    |    |    |    |    |    |    |    |     |     |     |     |     |     |     |     |     |

## MCU-Diagram - LED matrix

|   g  |   b  |   r  |  --- |  --- |  --- | col | C0 | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | C9 | C10 | C11 | C12 | C13 | C14 | C15 | C16 | C17 | C18 |
|  --- |  --- |  --- |  --- |  --- |  --- | --- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | --  | --  | --  | --  | --  | --  | --  | --  | --  |
|  ch1 |  ch2 |  ch3 |  pin |  pin |  pin | pin | 25 | 26 | 27 | 28 | 29 | 30 | 31 | 32 | 34 | 35 | 36  | 37  | 38  | 39  | 40  | 41  | 42  | 43  | 44  |
|  Q13 |  Q7  |  Q1  |  01  |  02  |  04  | --- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  Q14 |  Q8  |  Q2  |  05  |  06  |  07  | --- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  Q15 |  Q9  |  Q3  |  08  |  09  |  10  | --- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  Q16 |  Q10 |  Q4  |  11  |  12  |  13  | --- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  Q17 |  Q11 |  Q5  |  14  |  15  |  47  | --- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  Q18 |  Q12 |  Q6  |  50  |  49  |  48  | --- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## MCU-Diagram - mac/win and bt/off/cable dip switches

- Bluetooth / O / Cable Mode: pin 57
- Win - Android / Mac - iOS Mode: pin 58

## MCU-Diagram - Status LED indicators - K4 v2 only
- Caps Lock: pin 46
- Num Lock: pin 51

## MCU Pinout - SN32F248BF
![MCU-Pins](./img/MCU_SN32F248BF.png)

## Bluetooth module
![k4-bluetooth-CYW20730.png](./img/K4-bt-CYW20730.png)

seems to be wired like the Blitzwolf BW-KB1(https://github.com/IslamAlam/blitzwolf-bw-kb-1)
