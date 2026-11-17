# บทที่ 1: LLM ทำงานยังไง — token, context และการไม่จำ

ก่อนจะเข้าใจ agent, MCP หรือ plugin ต้องเข้าใจตัวที่อยู่ตรงกลางก่อน: **LLM (large language model)** บทนี้ไม่ลงคณิตศาสตร์ แต่ให้เห็นพฤติกรรมสามอย่างที่ทุกบทต่อจากนี้ต้องใช้ คือ token, context window และความจริงที่ว่า **model ไม่จำอะไรเลยระหว่างการเรียกแต่ละครั้ง**

ทุก output ในบทเรียนนี้รันจริงบน Ubuntu 24.04 (proot บน Android, aarch64) ด้วย Claude Code `2.1.325` — ชื่อ model ถูกแทนด้วย `<model>` และ path ถูกแทนด้วย `<cwd>`

---

## 1.1 LLM ทำอะไรจริง ๆ

> **คำอธิบาย (ไม่ใช่สิ่งที่สังเกตได้จากเครื่อง):** LLM คือโปรแกรมที่รับข้อความเข้าไป แล้วทำนาย "ชิ้นถัดไป" ของข้อความทีละชิ้น ซ้ำไปเรื่อย ๆ จนจบ มันเรียนรู้จากข้อความปริมาณมหาศาลว่าอะไรมักตามหลังอะไร คำตอบที่ดูฉลาดเกิดจากการทำนายแบบนี้

สามคำที่ต้องรู้:

| คำ | ความหมาย |
|---|---|
| **token** | หน่วยที่ model อ่านและเขียน — ไม่ใช่ตัวอักษร ไม่ใช่คำ แต่เป็นชิ้นส่วนของคำ (ภาษาอังกฤษราว 3–4 ตัวอักษรต่อ token ส่วนภาษาไทยมักใช้ token มากกว่าต่อความยาวเท่ากัน) |
| **context window** | จำนวน token สูงสุดที่ model "เห็น" ได้ในการเรียกหนึ่งครั้ง — ทั้งคำสั่ง ประวัติแชต ไฟล์ที่แนบ และคำตอบที่กำลังเขียน |
| **prompt** | ทุกอย่างที่ส่งเข้าไปในการเรียกหนึ่งครั้ง |

ค่าใช้จ่ายและความเร็วคิดตาม token: **input token** (ที่ส่งเข้า) กับ **output token** (ที่ model เขียนออกมา)

## 1.2 เรียก model แบบไม่มี agent: `claude -p`

Claude Code ปกติเป็นแชตโต้ตอบ แต่ `-p` (print) ส่งคำถามครั้งเดียวแล้วพิมพ์ผลออกมา ใช้แทน API ได้โดยไม่ต้องมี API key (ใช้ subscription เดิม) บทนี้ปิด tool ทั้งหมดด้วย `--tools ""` เพื่อให้เหลือ model ล้วน ๆ:

```sh
$ claude -p "My favourite number is 7. Reply with just: OK" \
    --output-format json --tools "" \
    --strict-mcp-config --setting-sources project --disable-slash-commands
```

| flag | ทำไม |
|---|---|
| `--output-format json` | ได้ผลเป็น JSON พร้อมตัวเลข token แทนข้อความล้วน |
| `--tools ""` | ไม่ให้ใช้ tool ใด ๆ (บทที่ 2 จะเปิด) |
| `--strict-mcp-config` | ไม่โหลด MCP server ที่ตั้งไว้ในเครื่อง |
| `--setting-sources project` | ไม่โหลด settings ระดับผู้ใช้ (plugin, hook ส่วนตัว) |
| `--disable-slash-commands` | ไม่โหลด skill |

flag ชุดหลังมีไว้ให้ผลทดลองไม่ปนกับ setup ส่วนตัวในเครื่อง ใช้ซ้ำทั้งบทเรียน

JSON ที่ได้มี field ราว 27 ตัว ตัวที่ใช้บ่อย:

```text
result        'OK'
num_turns     1
usage         {'input_tokens': 2, 'cache_read_input_tokens': 649,
               'cache_creation_input_tokens': 2321, 'output_tokens': 146}
duration_ms   6677
session_id    <session>
```

ทำไม input มีแค่ 2 token ทั้งที่ประโยคยาวกว่านั้น? เพราะ input แบ่งเป็นสามส่วน:

| field | ความหมาย |
|---|---|
| `input_tokens` | ส่วนใหม่ที่ไม่ได้ cache |
| `cache_creation_input_tokens` | ส่วนที่เพิ่งถูกเขียนลง prompt cache (ครั้งแรกที่เห็น) |
| `cache_read_input_tokens` | ส่วนที่อ่านจาก cache (ข้อความเดิมที่เคยส่ง — ถูกและเร็วกว่า) |

รวมสามช่องได้ราว 2,970 token สำหรับคำถามสั้น ๆ ประโยคเดียว เพราะ Claude Code ส่ง **system prompt** (คำสั่งเบื้องหลังว่าตัวเองเป็นใคร ทำอะไรได้) ไปด้วยทุกครั้ง ส่วนใหญ่ของ prompt จึงไม่ใช่สิ่งที่เราพิมพ์

`output_tokens` 146 ทั้งที่ตอบแค่ `OK` เพราะนับรวม "thinking" (การคิดก่อนตอบ) ที่ model เขียนแต่ไม่แสดงด้วย

## 1.3 model ไม่จำ — ทดลองให้เห็น

เรียกใหม่อีกครั้ง ถามสิ่งที่เพิ่งบอกไป:

```sh
$ claude -p "What is my favourite number? If you don't know, say 'I don't know'." \
    --output-format json --tools "" --strict-mcp-config --setting-sources project --disable-slash-commands
```

```text
result  "I don't know. I checked my saved memories and there's nothing recorded
         about your favourite number. If you tell me, I can save it for future sessions."
usage   {'input_tokens': 2, 'cache_read_input_tokens': 2427,
         'cache_creation_input_tokens': 549, 'output_tokens': 461}
```

ไม่รู้ — เพราะการเรียกครั้งที่สองเป็น **การเรียกใหม่ที่ไม่มีประวัติ** model ไม่มีที่เก็บความจำระหว่างการเรียก (คำว่า "saved memories" ในคำตอบคือฟีเจอร์ auto-memory ของ Claude Code ที่เก็บโน้ตเป็นไฟล์ แยกจากตัว model — ครั้งนี้ไม่มีโน้ตเรื่องนี้)

ทีนี้ให้ Claude Code **ส่งประวัติของครั้งแรกไปด้วย** ด้วย `--resume <session_id>`:

```sh
$ claude -p "What is my favourite number? If you don't know, say 'I don't know'." \
    --resume <session> --output-format json --tools "" ...
```

```text
result  '7'
usage   {'input_tokens': 4, 'cache_read_input_tokens': 2970,
         'cache_creation_input_tokens': 171, 'output_tokens': 3}
```

ตอบได้ และดูตัวเลข: `cache_read_input_tokens` = **2970** ตรงกับขนาด prompt ทั้งหมดของครั้งแรก (2 + 649 + 2321 = 2972 ใกล้เคียงกัน) แปลว่าบทสนทนาครั้งแรกทั้งก้อนถูกส่งกลับเข้าไปใหม่

!!! note "ข้อสรุปที่สำคัญที่สุดของบทนี้"
    "ความจำ" ของแชตทุกตัว คือโปรแกรมรอบนอก **ส่งประวัติทั้งหมดซ้ำ** ทุกครั้งที่เรียก model ยิ่งคุยยาว prompt ยิ่งใหญ่ จนชน context window — Claude Code จึงต้องมีกลไก **compaction** (สรุปประวัติเก่าให้สั้นลง) ซึ่งจะเห็นในบทที่ 4

ผลทั้งสามครั้ง (ตัดข้อมูลส่วนตัวแล้ว) อยู่ที่ `labs/fixtures/ch1-memory.jsonl` และ `tests/test_ch1_fixture.py` ตรวจว่าตัวเลขในบทนี้ตรงกับไฟล์นั้น

## 1.4 ทำไมถามเหมือนเดิมแล้วได้คำตอบไม่เหมือนเดิม

> **คำอธิบาย:** ตอนเลือก token ถัดไป model ได้ "ความน่าจะเป็น" ของหลายตัวเลือก แล้วสุ่มเลือกตามความน่าจะเป็นนั้น (ไม่ได้เลือกตัวที่น่าจะเป็นที่สุดเสมอ) คำตอบจึงต่างกันได้ทุกครั้ง โดยเฉพาะคำตอบยาว

ผลที่ตามมาสำหรับคนเขียนโปรแกรม: **อย่าเขียน test ที่คาดหวังข้อความเป๊ะ ๆ จาก model** — ในบทเรียนนี้ test ทั้งหมดจึงใช้ model ปลอม (บทที่ 2) หรือ output ที่บันทึกไว้แล้ว (บทที่ 3)

## 1.5 แบบฝึกหัด 3 ข้อ + เช็คความเข้าใจ 2 ข้อ

### แบบฝึกหัด

1. รัน `claude -p "Say hi" --output-format json --tools "" ...` สองครั้งติดกัน เทียบ `cache_creation_input_tokens` กับ `cache_read_input_tokens` ของครั้งแรกกับครั้งที่สอง แล้วอธิบายว่าทำไมต่างกัน
2. ถามคำถามเดียวกันเป็นภาษาไทยกับภาษาอังกฤษ ความหมายเท่ากัน เทียบ `output_tokens` ของคำตอบที่ยาวใกล้เคียงกัน
3. ใช้ `--resume` ต่อบทสนทนาสามรอบ จด `cache_read_input_tokens` แต่ละรอบ แล้ววาดกราฟคร่าว ๆ ว่าโตแบบไหน

### เช็คความเข้าใจ

1. ถ้า model ไม่จำอะไรเลย แชตที่ "จำ" สิ่งที่พูดเมื่อ 10 ข้อความก่อนได้ ทำได้ยังไง และมีต้นทุนอะไร
2. ทำไมคำถามสั้นประโยคเดียวถึงใช้ input หลายพัน token ใน Claude Code

## สรุปบทที่ 1

- LLM ทำนาย token ถัดไปซ้ำ ๆ — token ไม่ใช่ตัวอักษรหรือคำ และคิดเงินตาม token
- context window คือทุกอย่างที่ model เห็นในการเรียกครั้งเดียว รวม system prompt ที่เราไม่ได้พิมพ์
- model ไม่จำระหว่างการเรียก "ความจำ" คือการส่งประวัติซ้ำ (`--resume` ทำให้เห็นตัวเลขตรง ๆ)
- prompt cache ทำให้ส่วนที่ซ้ำถูกลง แต่ยังกินพื้นที่ context เท่าเดิม
- คำตอบมีการสุ่ม จึงไม่ควร test ด้วยข้อความเป๊ะ ๆ จาก model จริง
