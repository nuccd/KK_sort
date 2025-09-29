import sys
import os
import shutil
import datetime
import configparser
import logging

# --- 配置默认值，用于生成新的 config.ini 文件 ---
def create_default_config(path):
    """创建并保存默认的 config.ini 文件"""
    default_config = configparser.ConfigParser()
    
    default_config['Paths'] = {
        'outfit_card_dir': 'E:/Koikatu/UserData/coordinate',
        'character_card_dir': 'E:/Koikatu/UserData/chara/female/others/pixiv_2025',
        'scene_card_dir': 'E:/Koikatu/UserData/studio/scene',
        'zipmod_target_dir': 'E:/Koikatu/mods/mymods'
    }
    
    default_config['Options'] = {
        'is_copy': 'False',
        'update_file_time': 'True'
    }
    
    default_config['Logging'] = {
        'log_dir': './logs',
        'log_filename': 'koikatsu_sort_log_{date}.log',
        'log_level': 'INFO'
    }

    with open(path, 'w', encoding='utf-8') as configfile:
        default_config.write(configfile)


# --- 从 config.ini 读取配置 ---
config = configparser.ConfigParser()

# 确定脚本运行的基准路径 (兼容打包和未打包)
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后的路径：.exe 所在的目录
    base_path = os.path.dirname(sys.executable)
else:
    # .py 文件运行时的目录
    base_path = os.path.dirname(os.path.abspath(__file__))

# 外部 config.ini 的路径
config_path = os.path.join(base_path, 'config.ini')

# 检查外部配置文件是否存在。如果不存在，则自动生成一个。
if not os.path.exists(config_path):
    print(f"配置文件 '{os.path.basename(config_path)}' 不存在，正在自动生成默认模板...")
    create_default_config(config_path)
    print("默认配置文件已生成。请修改配置后再次运行脚本。")
    input("按任意键退出......")
    sys.exit()

# 读取配置文件
config.read(config_path)


# --- 初始化日志系统 ---
try:
    log_dir = config.get('Logging', 'log_dir', fallback='./logs')
    # 修正：确保默认 fallback 也是你要求的 sort log
    log_filename_template = config.get('Logging', 'log_filename', fallback='koikatsu_sort_log_{date}.log') 
    log_level_str = config.get('Logging', 'log_level', fallback='INFO').upper()
    log_level = getattr(logging, log_level_str)

    # 确保日志目录是相对 .exe 所在目录的
    if not os.path.isabs(log_dir):
        log_dir = os.path.join(base_path, log_dir)
    
    os.makedirs(log_dir, exist_ok=True)
    today = datetime.date.today().strftime('%Y-%m-%d')
    log_filename = log_filename_template.format(date=today)
    log_path = os.path.join(log_dir, log_filename)

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
except (configparser.NoSectionError, configparser.NoOptionError):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logging.warning("配置文件中未找到 [Logging] 部分或选项，使用默认日志设置。")

# --- 配置部分 ---
try:
    outfit_card_dir = config.get('Paths', 'outfit_card_dir')
    character_card_dir = config.get('Paths', 'character_card_dir')
    scene_card_dir = config.get('Paths', 'scene_card_dir')
    zipmod_target_dir = config.get('Paths', 'zipmod_target_dir')
    is_copy = config.getboolean('Options', 'is_copy')
    update_file_time = config.getboolean('Options', 'update_file_time', fallback=True) 
except configparser.NoSectionError as e:
    logging.critical(f"配置文件中缺少关键配置段，请检查 'config.ini' 文件：{e}")
    input("按任意键退出......")
    sys.exit()

# 确保所有目标目录都存在
os.makedirs(outfit_card_dir, exist_ok=True)
os.makedirs(character_card_dir, exist_ok=True)
os.makedirs(scene_card_dir, exist_ok=True) 
os.makedirs(zipmod_target_dir, exist_ok=True)


# --- 功能方法部分 ---

def get_card_type(file_path):
    """
    通过检查PNG文件的二进制签名来判断卡片类型。
    返回 'character', 'outfit', 'scene', 或 None。
    """
    try:
        with open(file_path, 'rb') as f:
            file_content = f.read()
            
            # PNG 文件结束块的签名
            iend_chunk_signature = b'IEND\xae\x42\x60\x82'
            
            # 查找 IEND 数据块的位置
            iend_index = file_content.find(iend_chunk_signature)
            
            if iend_index == -1:
                return None
            
            # 从 IEND 块之后开始读取卡片数据签名
            start_index = iend_index + len(iend_chunk_signature) + 8
            
            slice_length = 14
            
            # 检查文件大小是否足以包含签名
            if len(file_content) < start_index + slice_length:
                return None
            
            data_signature = file_content[start_index : start_index + slice_length]
            
            # 1. 判断角色卡 (优先级最高)
            if data_signature.startswith(b'KoiKatuChara'):
                return 'character'
            # 2. 判断服装卡 (优先级次之)
            elif data_signature.startswith(b'KoiKatuClothes'):
                return 'outfit'
            # 3. 最后判断场景卡 (如果前两者都不是，且包含场景卡特征)
            elif b'RendererPropertyList' in file_content: 
                return 'scene'
            
    except Exception as e:
        logging.warning(f"处理图片 '{os.path.basename(file_path)}' 时发生错误：{e}")
        return None
    
    return None

def process_file(source_path, destination_dir, file_name, times):
    """
    根据配置is_copy来决定是复制还是移动文件，并处理文件时间戳。
    """
    destination_path = os.path.join(destination_dir, file_name)
    
    # 直接使用全局的 is_copy 变量进行判断和操作
    if is_copy:
        # 复制操作
        shutil.copy2(source_path, destination_path)
        logging.info(f"   -> 已将文件复制到：{destination_dir}")
    else:
        # 移动操作 
        shutil.move(source_path, destination_path)
        logging.info(f"   -> 已将文件移动到：{destination_dir}")
    
    # 根据配置决定是否更新文件时间
    if update_file_time:
        current_time = datetime.datetime.now().timestamp()
        os.utime(destination_path, (current_time, current_time))
        logging.info(f"   -> 已将文件修改日期更新为当前时间。")
    else:
        # 补充日志，明确说明没有更新时间
        logging.info(f"   -> 保留文件原始修改日期。")

def process_image(file_path, file_name, times):
    """
    根据文件结构判断卡片类型并处理文件。
    """
    card_type = get_card_type(file_path)
    
    if card_type == 'character':
        logging.info(f"{times}. '{file_name}' 是角色卡。")
        process_file(file_path, character_card_dir, file_name, times)
    elif card_type == 'outfit':
        logging.info(f"{times}. '{file_name}' 是服装卡。")
        process_file(file_path, outfit_card_dir, file_name, times)
    elif card_type == 'scene':
        logging.info(f"{times}. '{file_name}' 是场景卡。")
        process_file(file_path, scene_card_dir, file_name, times)
    else:
        logging.warning(f"{times}. '{file_name}' 不是有效的恋活卡片，未处理。")
        return

def process_zipmod(file_path, file_name, times):
    """
    处理 zipmod 文件。它会遵从全局 is_copy 设置。
    """
    logging.info(f"{times}. '{file_name}' 是 zipmod 文件。")
    # 调用 process_file，它会根据 is_copy 配置决定复制还是移动
    process_file(file_path, zipmod_target_dir, file_name, times)
    

# --- 主程序逻辑 ---

def main():
    # 调试模式: 在这里设置你要测试的特定文件路径 
    # 如果 sys.argv 只有一个元素（脚本本身），则使用下面的列表 
    # 你可以添加多个文件路径到这个列表中
    files_to_process = [
        r'E:\Koikatu\_shortcut\kk_sort\test\chara.png',
        r'E:\Koikatu\_shortcut\kk_sort\test\outfit.png',
        r'E:\Koikatu\_shortcut\kk_sort\test\scene.png', 
        r'E:\Koikatu\_shortcut\kk_sort\test\mods.zipmod',
    ]

    # 根据是否有拖放文件来决定使用哪种模式，创建一个新的列表，包含从 sys.argv 的第二个元素（索引为 1）开始，一直到列表末尾的所有元素。
    if len(sys.argv) > 1:
        file_paths = sys.argv[1:]
    else:
        file_paths = files_to_process
        logging.info("以调试模式运行...")
        is_copy = True

    logging.info(f"正在处理 {len(file_paths)} 个文件...")
    
    times = 0
    for file_path in file_paths:
        if not os.path.isfile(file_path):
            logging.warning(f"警告：'{file_path}' 不是一个有效的文件，跳过。")
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
                logging.warning(f"{times}. '{file_name}' 是未知文件类型 '{file_extension}'，未移动。")
                
        except Exception as e:
            logging.error(f"处理文件 '{file_name}' 时发生错误：{e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 记录任何未捕获的错误
        logging.critical(f"脚本发生致命错误：{e}")
    finally:
        # 无论是否发生错误，都执行这行代码
        input("按任意键退出......")