# -*- coding: utf-8 -*-
"""
修复 settings_dialog.py 中的缩进错误
"""
import os
import re

def fix_indentation_issues():
    """修复 settings_dialog.py 中的缩进问题"""
    file_path = r"d:\Person_project\AI_IDE_Auto_Run_github_main_V4.2\auto_approve\settings_dialog.py"
    
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 修复缩进问题的函数
    def fix_line_indentation(line, line_num):
        """修复单行的缩进问题"""
        # 移除行尾的空白字符
        line = line.rstrip() + '\n'
        
        # 如果是空行，直接返回
        if line.strip() == '':
            return '\n'
        
        # 检查并修复函数定义的缩进
        if line.strip().startswith('def '):
            # 如果在类中，应该是4个空格缩进
            if any('class ' in prev_line for prev_line in lines[max(0, line_num-50):line_num]):
                return '    ' + line.lstrip()
        
        # 检查并修复其他语句的缩进
        stripped = line.lstrip()
        if stripped:
            # 计算当前缩进级别
            indent_level = len(line) - len(stripped)
            
            # 确保缩进是4的倍数
            if indent_level % 4 != 0:
                # 调整到最近的4的倍数
                correct_indent = (indent_level // 4) * 4
                if indent_level % 4 >= 2:
                    correct_indent += 4
                line = ' ' * correct_indent + stripped
        
        return line
    
    # 修复所有行的缩进
    fixed_lines = []
    for i, line in enumerate(lines):
        fixed_line = fix_line_indentation(line, i)
        fixed_lines.append(fixed_line)
    
    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)
    
    print("缩进修复完成")

if __name__ == "__main__":
    fix_indentation_issues()
