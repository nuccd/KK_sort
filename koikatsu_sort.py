import sys
import os
import shutil
import datetime
import configparser

# --- 从 config.ini 读取配置 ---
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
config.read(config_path)

# --- 配置部分 ---
outfit_card_dir = config.get('Paths', 'outfit_card_dir')
character_card_dir = config.get('Paths', 'character_card_dir')
zipmod_target_dir = config.get('Paths', 'zipmod_target_dir')

is_copy = config.getboolean('Options', 'is_copy')

# 确保所有目标目录都存在
os.makedirs(outfit_card_dir, exist_ok=True)
os.makedirs(character_card_dir, exist_ok=True)
os.makedirs(zipmod_target_dir, exist_ok=True)


# --- 功能方法部分 ---

def get_card_type(file_path):
    """
    通过检查PNG文件的二进制签名来判断卡片类型。
    返回 'character', 'outfit', 或 None。
    """
    try:
        with open(file_path, 'rb') as f:
            file_content = f.read()
            
            # 完整的 IEND 数据块签名（包含类型和CRC校验码）
            iend_chunk_signature = b'IEND\xae\x42\x60\x82'
            
            # 查找 IEND 数据块的位置
            iend_index = file_content.find(iend_chunk_signature)
            
            if iend_index == -1:
                return None  # 未找到 IEND 数据块，不是有效的PNG卡片
            
            # 从完整的 IEND 签名块的末尾（8字节）开始，再跳过你发现的8字节
            start_index = iend_index + len(iend_chunk_signature) + 8
            
            # 检查文件大小是否足以包含签名
            if len(file_content) < start_index + 14:
                return None
            
            data_signature = file_content[start_index : start_index + 14]
            
            if data_signature.startswith(b'KoiKatuChara'):
                return 'character'
            elif data_signature.startswith(b'KoiKatuClothes'):
                return 'outfit'
            
    except Exception as e:
        print(f"警告：处理图片 '{os.path.basename(file_path)}' 时发生错误：{e}")
        return None
    
    return None

def process_file(source_path, destination_dir, operation_type, file_name, times):
    """
    根据操作类型（移动或复制）来处理文件。
    """
    destination_path = os.path.join(destination_dir, file_name)
    
    if operation_type == 'move':
        shutil.move(source_path, destination_path)
        print(f"   -> 已将文件移动到：{destination_dir}")
    elif operation_type == 'copy':
        shutil.copy2(source_path, destination_path)
        print(f"   -> 已将文件复制到：{destination_dir}")
    
    current_time = datetime.datetime.now().timestamp()
    os.utime(destination_path, (current_time, current_time))
    print(f"   -> 已将文件修改日期更新为当前时间。")

def process_image(file_path, file_name, times):
    """
    根据文件结构判断卡片类型并处理文件。
    """
    card_type = get_card_type(file_path)
    
    if card_type == 'character':
        print(f"{times}. '{file_name}' 是角色卡。")
        process_file(file_path, character_card_dir, 'copy' if is_copy else 'move', file_name, times)
    elif card_type == 'outfit':
        print(f"{times}. '{file_name}' 是服装卡。")
        process_file(file_path, outfit_card_dir, 'copy' if is_copy else 'move', file_name, times)
    else:
        print(f"{times}. '{file_name}' 不是有效的角色卡或服装卡，未处理。")
        return

def process_zipmod(file_path, file_name, times):
    """
    处理 zipmod 文件。
    """
    print(f"{times}. '{file_name}' 是 zipmod 文件。")
    process_file(file_path, zipmod_target_dir, 'move', file_name, times)
    

# --- 主程序逻辑 ---

def main():
    # 调试模式: 在这里设置你要测试的特定文件路径
    # 如果 sys.argv 只有一个元素（脚本本身），则使用下面的列表
    # 你可以添加多个文件路径到这个列表中
    files_to_process = [
        r'E:\Koikatu\_shortcut\kk_sort\test\chara.png',
        r'E:\Koikatu\_shortcut\kk_sort\test\outfit.png',
        r'E:\Koikatu\_shortcut\kk_sort\test\mods.zipmod',
    ]

    # 根据是否有拖放文件来决定使用哪种模式，创建一个新的列表，包含从 sys.argv 的第二个元素（索引为 1）开始，一直到列表末尾的所有元素。
    if len(sys.argv) > 1:
        file_paths = sys.argv[1:]
    else:
        file_paths = files_to_process
        print("以调试模式运行...")

    print(f"正在处理 {len(file_paths)} 个文件...")
    
    times = 0
    for file_path in file_paths:
        if not os.path.isfile(file_path):
            print(f"警告：'{file_path}' 不是一个有效的文件，跳过。")
            continue
        
        times += 1
        file_name = os.path.basename(file_path)
        file_extension = os.path.splitext(file_name)[1].lower()
        
        try:
            if file_extension == '.png':
                process_image(file_path, file_name, times)
            
            elif file_extension == '.zipmod':
                process_zipmod(file_path, file_name, times)
            
            else:
                print(f"{times}. '{file_name}' 是未知文件类型 '{file_extension}'，未移动。")
                
        except Exception as e:
            print(f"处理文件 '{file_name}' 时发生错误：{e}")

if __name__ == "__main__":
    main()    
    input("按任意键退出......")