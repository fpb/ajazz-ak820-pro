# AJAZZ AK820 Pro reverse engineering

This is just a way to document my findings regarding the board of my AJAZZ AK820 Pro (BT/USB/2.4G 81 keys)

## TODO List - Perhaps some kind souls will add QMK support for it
- [x] map lcd module connections
- [x] check connections

## Chips
* Main MCU - HFD80CP100 - appears to be based on/clone of [SONIX SN32F99](https://www.sonix.com.tw/article-jp-4797-39755)
![mcu-hfd](./img/mcu-hfd.png)

* Bt module [WCH CH582F]([https://www.infinite-electronic.ru/datasheet/2a-CYW20730A2KFBG.pdf](https://www.wch-ic.com/products/CH583.html?)https://www.wch-ic.com/products/CH583.html?)
* [ak820-bt](./img/ak820-bt.png)

* External 16MB flash module [PY25Q128HA](https://puyasemi.com/uploadfiles/2022/09/20220913130446446.pdf)

* LCD Module - 0.85" 128x128 [NFP085B-10AF](https://cdn.hackaday.io/files/1881838051221472/GC9107%20DataSheet%20V1.2.pdf)

## Key Matrix & MCU
<img width="912" alt="image" src="https://github.com/fpb/ajazz-820-pro/assets/456959/47b6e33f-249f-44f9-92f7-060f192f8aa1">

