import os
import struct
import sys

def unescape(s):
    return s.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')

def compile_po(po_file, mo_file):
    print(f"Compiling {po_file} -> {mo_file}")
    with open(po_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    messages = {}
    current_msgid = None
    current_msgstr = None
    
    # State: 0=none, 1=msgid, 2=msgstr
    state = 0
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
            
        if line.startswith('msgid "'):
            if current_msgid is not None and current_msgstr is not None:
                messages[unescape(current_msgid)] = unescape(current_msgstr)
            current_msgid = line[7:-1]
            current_msgstr = None
            state = 1
        elif line.startswith('msgstr "'):
            current_msgstr = line[8:-1]
            state = 2
        elif line.startswith('"'):
            # Continuation
            content = line[1:-1]
            if state == 1 and current_msgid is not None:
                current_msgid += content
            elif state == 2 and current_msgstr is not None:
                current_msgstr += content

    # Add last message
    if current_msgid is not None and current_msgstr is not None:
        messages[unescape(current_msgid)] = unescape(current_msgstr)

    # Do NOT remove empty msgid (header) as it contains charset info!
    # if "" in messages:
    #     del messages[""]

    # Sort messages
    sorted_msgs = sorted(messages.items())
    N = len(sorted_msgs)
    
    O_table_offset = 28 # Header size
    T_table_offset = O_table_offset + (8 * N)
    Strings_offset = T_table_offset + (8 * N)
    
    O_table = []
    T_table = []
    data = bytearray()
    
    for msgid, msgstr in sorted_msgs:
        msgid_encoded = msgid.encode('utf-8')
        msgstr_encoded = msgstr.encode('utf-8')
        
        O_table.append((len(msgid_encoded), Strings_offset + len(data)))
        data.extend(msgid_encoded)
        data.append(0) # Null terminator
        
        T_table.append((len(msgstr_encoded), Strings_offset + len(data)))
        data.extend(msgstr_encoded)
        data.append(0) # Null terminator

    # Write MO file
    with open(mo_file, 'wb') as f:
        # Magic number
        f.write(struct.pack('<I', 0x950412de))
        # Revision
        f.write(struct.pack('<I', 0))
        # N
        f.write(struct.pack('<I', N))
        # O offset
        f.write(struct.pack('<I', O_table_offset))
        # T offset
        f.write(struct.pack('<I', T_table_offset))
        # Hash size (0)
        f.write(struct.pack('<I', 0))
        # Hash offset (0)
        f.write(struct.pack('<I', 0))
        
        # O table
        for length, offset in O_table:
            f.write(struct.pack('<II', length, offset))
            
        # T table
        for length, offset in T_table:
            f.write(struct.pack('<II', length, offset))
            
        # Strings
        f.write(data)

if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    locale_dir = os.path.join(base_dir, 'locale')
    
    for lang in os.listdir(locale_dir):
        lc_messages = os.path.join(locale_dir, lang, 'LC_MESSAGES')
        if os.path.isdir(lc_messages):
            po_file = os.path.join(lc_messages, 'django.po')
            mo_file = os.path.join(lc_messages, 'django.mo')
            if os.path.exists(po_file):
                try:
                    compile_po(po_file, mo_file)
                    print(f"Successfully compiled {lang}")
                except Exception as e:
                    print(f"Error compiling {lang}: {e}")
