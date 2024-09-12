import os, logging,math

SCALE = 1.0

def distance(point1, point2):
    """计算两点之间的欧氏距离"""
    return math.sqrt((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2)

def insert_points(points, max_distance=5):
    """在两点之间插入点,如果它们之间的距离超过max_distance"""
    new_points = [points[-1]]  # 从原点列表中添加第一个点
    for i in range(0, len(points)):
        current_point = points[i]
        last_point = new_points[-1]
        
        # 计算当前点与上一个点的距离
        if round(distance(current_point, last_point),2) > max_distance:
            # 计算需要插入多少个点
            num_points_to_insert = math.ceil(distance(current_point, last_point) / max_distance)
            # 计算每个点的间隔
            interval = round(distance(current_point, last_point) / num_points_to_insert,2)
            
            # 插入点
            for j in range(1, num_points_to_insert):
                new_x = last_point[0] + (current_point[0] - last_point[0]) * (j / num_points_to_insert)
                new_y = last_point[1] + (current_point[1] - last_point[1]) * (j / num_points_to_insert)
                new_point = (round(new_x,2), round(new_y,2))
                new_points.append(new_point)
            
            # 添加当前点
            new_points.append(current_point)
        else:
            # 如果不需要插入点，直接添加当前点
            new_points.append(current_point)
    
    return new_points

def parse_string(ch, word): #flsun add
    start = word.index(ch) + 1 # get first ch position
    if ' ' in word[start:]:
        end = word.index(' ', start, -1)
        num_str = word[start:end]
    else:
        end = -1
        num_str = word[start:]
    num = float(num_str)
    return num

def generate_edge_points(filename):
    '''从传入的文件中，取首层外边沿，生成各边沿通道的坐标集合'''
    layer_change = ";LAYER_CHANGE"
    layer_first_cura = ";LAYER:0"
    layer_other_cura = ";LAYER:1"
    wall_text = ";TYPE:External perimeter" #prusa slicer wall out start position
    wall_cura_text = ";TYPE:WALL-OUTER"    #cura wall out start position
    wall_end_text = ";TYPE:" # wall out end position
    wall_detect = False
    edge_points = []
    channel_edge_points = []
    x_coor = 0.0
    y_coor = 0.0
    layer = 0
    last_xy = None
    with open(filename) as file_ob:
        for line in file_ob:
            word = line.rstrip()
            # 如果在0层，切到第一层
            if (layer_change in word  or layer_first_cura in word ) and layer == 0 :
                layer = 1
            # 其他层，直接跳过
            elif layer_change in word or layer_other_cura in word:
                break

            # 如果尚未识别外墙段，则始终保存最新一条G1命令
            if not wall_detect and ("G1 " in word or "G0 " in word):
                if " X" in word or " Y" in word:
                    if "X" in word:
                        x_coor = parse_string('X', word)
                    if "Y" in word:
                        y_coor = parse_string('Y', word)
                    last_xy = (x_coor,y_coor)

            #外墙识别
            if wall_text in word  or wall_cura_text in word:
                wall_detect = True
                if last_xy:
                    edge_points.append(last_xy)
                continue

            #外墙结束
            elif wall_detect and wall_end_text in word:
                channel_edge_points.append(edge_points)
                edge_points = []
                wall_detect = False
                continue

            if  wall_detect and "G1 " in word and (" X" in word or " Y" in word):
                if "X" in word:
                    x_coor = parse_string('X', word)
                if "Y" in word:
                    y_coor = parse_string('Y', word)
                edge_points.append((x_coor,y_coor))

    for channel in channel_edge_points:
        channel.pop(-1)

    return channel_edge_points

"""从传入文件中取点，并进行插点处理，然后等间隔取nums个点"""
def get_edge_points(filename,nums=16, x_offset=0., y_offset=0.):
    insert_threshold = 2
    ext_edge_points_all = []
    #根据文件名读取首层边沿点
    first_channel_layer_edge_points = generate_edge_points(filename)
    #first_layer_edge_points.pop(-1)
    for first_layer_edge_points in first_channel_layer_edge_points:
        # 如果首层点数较少
        #if len(first_layer_edge_points) < nums :
        #    insert_threshold = 1   
        # 拆分距离较长的线段，每5mm插入插入一个新点
        ext_edge_points = insert_points(first_layer_edge_points, insert_threshold)
        ext_edge_points_all += ext_edge_points

    # 从扩展结果中均匀的选nums个点
    step = len(ext_edge_points_all)//nums
    sparse_points = []
    for i in range(nums,0,-1):
        index = len(ext_edge_points_all) - step*i
        sparse_points.append(ext_edge_points_all[index])

    res_points = []
    new_res_points = []
    for res_point in sparse_points:
        new_point = list(res_point)
        # 缩放为原始点的SCALE倍
        new_point[0] = round(new_point[0]*SCALE,2)
        new_point[1] = round(new_point[1]*SCALE,2) 

        #融入偏移
        new_point[0] =round(new_point[0] - x_offset,2)
        new_point[1] =round(new_point[1] - y_offset,2)

        while (new_point[0]**2 + new_point[1]**2 > 160*160):
            new_point[1] += 3
            if new_point[1] > -6 and new_point[1] < 6:
                break
        
        new_res_points.append((new_point[0],new_point[1]))
        res_points.append(new_point)

    return res_points
