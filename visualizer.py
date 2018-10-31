import random
import hashlib
import matplotlib as mpl
mpl.use('TkAgg')
import matplotlib.pyplot as plt
import numpy as np
import networkx as nx
from blocks import Block, SwitchMessage_BecomeAParent, SwitchMessage_ChangeParent, SwitchMessage_Orbit
from config import *
import copy

from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
#Image.open('image.jpg').load()

import os
import imageio as io
from PIL import Image


BASE = 10000000
IMAGE_LIMIT = 500
FRAMES = "graphs/"
THUMBNAILS = "thumbs/"
COLOURS = ["LightYellow", "Yellow", "Orange", "OrangeRed", "Red", "DarkRed", "Black"]


def blocks_by_shard_display_height(blocks):
    heights = {}
    blocks_by_height = {}
    unsorted_blocks = blocks
    for b in unsorted_blocks:
        # Root shard has no parent
        if b.parent_ID is None:
            heights[b] = 0
            blocks_by_height[0] = [b]
            unsorted_blocks.remove(b)
            break

    while len(unsorted_blocks) > 0:
        for b in unsorted_blocks:
            # If we have the height of their parent
            if b.parent_ID in heights.keys():
                # Then we can assign their height (parent height + 1)
                heights[b] = 1 + heights[b.parent_ID]

                if heights[b] not in blocks_by_height.keys():
                    blocks_by_height[heights[b]] = [b]
                else:
                    blocks_by_height[heights[b]].append(b)

                unsorted_blocks.remove(b)

    return blocks_by_height


# This function returns a map from height to a list of shards
def sort_blocks_by_shard_height(fork_choice_by_shard):

    for b in fork_choice_by_shard.values():
        assert isinstance(b, Block), "expected only blocks"

    for ID in fork_choice_by_shard.keys():
        assert ID in SHARD_IDS, "expected shard ID"

    root_shard_tip = None
    for b in fork_choice_by_shard.values():
        # Root shard has no parent
        if b.parent_ID is None:
            root_shard_tip = b
            break

    fork_choice_by_height = {}
    if root_shard_tip is not None:
        ret = recur_sort_shards(fork_choice_by_shard, [root_shard_tip], 0, fork_choice_by_height)
    else:
        ret = recur_sort_shards(fork_choice_by_shard, [fork_choice_by_shard[0],fork_choice_by_shard[1]], 0, fork_choice_by_height)

    extra_height = max(list(ret.keys())) + 1
    all_shards = [x.shard_ID for x in sum(ret.values(), [])]

    for shard_ID in SHARD_IDS:
        if shard_ID not in all_shards:
            if extra_height not in ret:
                ret[extra_height] = []
            ret[extra_height].append(fork_choice_by_shard[shard_ID])

    return ret


# Implements a depth first search of the shard tree
# The order of the search is determined by 'sorted' of shard_IDs
def recur_sort_shards(fork_choice_by_shard, sorted_children, height, fork_choice_by_height, on_stack=None):
    if sorted_children == []:
        return

    if on_stack is None:
        on_stack = set()

    for b in sorted_children:
        assert isinstance(b, Block), "expected children to be blocks"

    for child in sorted_children:
        if child in on_stack:
            continue

        on_stack.add(child)

        if height not in fork_choice_by_height.keys():
            fork_choice_by_height[height] = [child]
        else:
            fork_choice_by_height[height].append(child)

        sorted_child_IDs = sorted(child.child_IDs)
        children = []
        for i in range(len(sorted_child_IDs)):
            children.append(fork_choice_by_shard[sorted_child_IDs[i]])

        recur_sort_shards(fork_choice_by_shard, children, height + 1, fork_choice_by_height, on_stack)

        on_stack.remove(child)

    return fork_choice_by_height

def init_plt(figsize=(30,20)):
    plt.figure(figsize=(30,20))



def report(watcher, round_number, genesis_blocks):
    plt.clf()

    # OUTSIDE BORDER BOX
    GraphBorder = nx.Graph();
    CornersPos = {}
    CornersPos["topleft"] = (0, 0)
    CornersPos["topright"] = (DISPLAY_WIDTH, 0)
    CornersPos["bottomleft"] = (0, DISPLAY_HEIGHT)
    CornersPos["bottomright"] = (DISPLAY_WIDTH,  DISPLAY_HEIGHT)

    GraphBorder.add_node("topleft")
    GraphBorder.add_node("topright")
    GraphBorder.add_node("bottomleft")
    GraphBorder.add_node("bottomright")
    GraphBorder.add_edge("topright", "topleft")
    GraphBorder.add_edge("topright", "bottomright")
    GraphBorder.add_edge("topleft", "bottomleft")
    GraphBorder.add_edge("bottomleft", "bottomright")

    nx.draw_networkx_nodes(GraphBorder, CornersPos, node_size=0)
    nx.draw_networkx_edges(GraphBorder, CornersPos, width=1.5)


    # SHARD BOXES
    ShardBorder = nx.Graph();

    # The position of the shards may vary, so we get them from the fork choice:
    fork_choice = watcher.make_all_fork_choices(genesis_blocks)
    print("vvvvvvv")
    for k, v in fork_choice.items():
        print("%s => %s, %s, %s" % (k, v.parent_ID, v.child_IDs, v.routing_table))
    print("^^^^^^^")

    fork_choice_by_shard_height = sort_blocks_by_shard_height(fork_choice)

    num_layers = len(fork_choice_by_shard_height.keys())

    num_shards_by_height = {}
    for i in range(num_layers):
        num_shards_by_height[i] = len(fork_choice_by_shard_height[i])

    shard_display_width_by_height = {}
    for i in range(num_layers):
        shard_display_width_by_height[i] = (DISPLAY_WIDTH - 2*DISPLAY_MARGIN - (num_shards_by_height[i] - 1)*SHARD_X_SPACING)/num_shards_by_height[i]

    shard_display_height = (DISPLAY_HEIGHT - 2*DISPLAY_MARGIN - (num_layers - 1)*SHARD_Y_SPACING)/num_layers

    ShardBorderPos = {}
    print("vvvv")
    for h in range(num_layers):
        y_top = DISPLAY_HEIGHT - (DISPLAY_MARGIN + h*(shard_display_height + SHARD_Y_SPACING))
        y_bottom = y_top - shard_display_height
        for i in range(len(fork_choice_by_shard_height[h])):
            assert isinstance(fork_choice_by_shard_height[h][i], Block), "expected block"
            shard_ID = fork_choice_by_shard_height[h][i].shard_ID
            print(shard_ID, end="")

            ShardBorder.add_node((shard_ID, "topleft"))
            ShardBorder.add_node((shard_ID, "topright"))
            ShardBorder.add_node((shard_ID, "bottomleft"))
            ShardBorder.add_node((shard_ID, "bottomright"))
            ShardBorder.add_edge((shard_ID, "topleft"), (shard_ID, "topright"))
            ShardBorder.add_edge((shard_ID, "topleft"), (shard_ID, "bottomleft"))
            ShardBorder.add_edge((shard_ID, "topright"), (shard_ID, "bottomright"))
            ShardBorder.add_edge((shard_ID, "bottomleft"), (shard_ID, "bottomright"))

            x_left = DISPLAY_MARGIN + i*(shard_display_width_by_height[h] + SHARD_X_SPACING)
            x_right = x_left + shard_display_width_by_height[h]

            ShardBorderPos[(shard_ID, "topleft")] = (x_left, y_top)
            ShardBorderPos[(shard_ID, "topright")] = (x_right, y_top)
            ShardBorderPos[(shard_ID, "bottomleft")] = (x_left, y_bottom)
            ShardBorderPos[(shard_ID, "bottomright")] = (x_right, y_bottom)
        print()

    print("^^^^")
    nx.draw_networkx_nodes(ShardBorder, ShardBorderPos, node_size=0)
    nx.draw_networkx_edges(ShardBorder, ShardBorderPos, width=1)


    # SHARD LAYOUT

    ShardLayout = nx.Graph()
    for ID in SHARD_IDS:
        ShardLayout.add_node(ID)

    for block in fork_choice.values():
        if block.parent_ID is not None:
            ShardLayout.add_edge(block.parent_ID, block.shard_ID)

    labels = {}
    ShardPos = {}
    for shard_ID in SHARD_IDS:
        x = (ShardBorderPos[(shard_ID, "topleft")][0] + ShardBorderPos[(shard_ID, "topright")][0])/2  - DISPLAY_HEIGHT
        y = (ShardBorderPos[(shard_ID, "topleft")][1] + ShardBorderPos[(shard_ID, "bottomleft")][1])/2
        ShardPos[shard_ID] = (x/2, y/2 + DISPLAY_HEIGHT/4)
        labels[shard_ID] = shard_ID

    nx.draw_networkx_nodes(ShardLayout, ShardPos, node_color='#e6f3f7', edge_color='b', node_size=4000)
    nx.draw_networkx_edges(ShardLayout, ShardPos, alpha=0.5, edge_color='b', width=10)
    nx.draw_networkx_labels(ShardLayout,pos=ShardPos, label=labels, font_size=40)



    # VALIDATOR LINES
    ValidatorLines = nx.Graph();
    for v in VALIDATOR_NAMES:
        if v != 0:
            ValidatorLines.add_node((v, "left"))
            ValidatorLines.add_node((v, "right"))
            ValidatorLines.add_edge((v, "left"), (v, "right"))  


    validator_y_coordinate = {}
    validator_left_x_coordinate = {}
    ValidatorLinePoS = {}
    for ID in SHARD_IDS:
        x_left = ShardBorderPos[(ID, "topleft")][0] + DISPLAY_MARGIN
        x_right = ShardBorderPos[(ID, "topright")][0] - DISPLAY_MARGIN


        num_validators = len(SHARD_VALIDATOR_ASSIGNMENT[ID])
        validator_y_spacing = (1.)/(num_validators + 1)

        for i in range(num_validators):
            v = SHARD_VALIDATOR_ASSIGNMENT[ID][i]
            relative_validator_display_height = (i + 1)*validator_y_spacing

            validator_y_coordinate[v] = ShardBorderPos[(ID, "topleft")][1] - shard_display_height*relative_validator_display_height
            validator_left_x_coordinate[v] = x_left

            y = validator_y_coordinate[v]

            ValidatorLinePoS[(v, "left")] = (x_left, y)
            ValidatorLinePoS[(v, "right")] = (x_right, y)


    nx.draw_networkx_nodes(ValidatorLines, ValidatorLinePoS, node_size=0)
    nx.draw_networkx_edges(ValidatorLines, ValidatorLinePoS, width=0.25)


    # PREVBLOCK POINTERS, FORK CHOICE AND SOURCES
    X_SPACE_PER_MESSAGE_HEIGHT = (DISPLAY_WIDTH - 2*DISPLAY_MARGIN)/CONSENSUS_MESSAGE_HEIGHTS_TO_DISPLAY_IN_ROOT

    window_size_by_shard_height = {}

    for h in range(num_layers):
        window_size_by_shard_height[h] = shard_display_width_by_height[h]/(X_SPACE_PER_MESSAGE_HEIGHT) + 4


    max_message_display_height_by_shard = {}
    for ID in SHARD_IDS:
        max_message_display_height_by_shard[ID] = 0

    for m in watcher.consensus_messages:
        if max_message_display_height_by_shard[m.estimate.shard_ID] < m.height:
            max_message_display_height_by_shard[m.estimate.shard_ID] = m.height

    shard_display_height_by_shard_ID = {}
    for h in range(num_layers):
        for b in fork_choice_by_shard_height[h]:
            shard_display_height_by_shard_ID[b.shard_ID] = h

    # messages in the shard windows
    displayable_messages = []
    for m in watcher.consensus_messages:
        # checks if m is in the display window for its shard
        ID = m.estimate.shard_ID
        shard_height = shard_display_height_by_shard_ID[ID]
        if m.height >= max_message_display_height_by_shard[ID] - window_size_by_shard_height[shard_height]:
            displayable_messages.append(m)

    # prevblock pointers, fork choices, and sources
    PrevblockGraph = nx.DiGraph();
    ForkChoiceGraph = nx.DiGraph();
    SourcesGraph = nx.DiGraph();

    messagesPos = {}
    senders = {}
    block_to_message = {}

    for m in displayable_messages:
        PrevblockGraph.add_node(m)
        ForkChoiceGraph.add_node(m)
        SourcesGraph.add_node(m)

        ID = m.estimate.shard_ID
        shard_height = shard_display_height_by_shard_ID[ID]

        if max_message_display_height_by_shard[ID] > window_size_by_shard_height[shard_display_height_by_shard_ID[ID]]:
            start_of_window = max_message_display_height_by_shard[ID] - window_size_by_shard_height[shard_height]
        else:
            start_of_window = 0

        used_window = max_message_display_height_by_shard[ID] - start_of_window
        relative_height = (m.height - start_of_window - 1)/used_window

        # get positions:
        assert relative_height <= 1, "expected relative height to be less than 1"
        xoffset = relative_height*(shard_display_width_by_height[shard_height] - 2*DISPLAY_MARGIN) + DISPLAY_MARGIN

        if m.sender != 0:
            messagesPos[m] = (validator_left_x_coordinate[m.sender] + xoffset, validator_y_coordinate[m.sender])
        else:
            x = ShardBorderPos[(m.estimate.shard_ID, "topleft")][0] + DISPLAY_MARGIN
            y = (ShardBorderPos[(m.estimate.shard_ID, "topleft")][1] + ShardBorderPos[(m.estimate.shard_ID, "bottomleft")][1])/2
            messagesPos[m] = (x, y)


        # this map will help us draw nodes from prevblocks, sources, etc
        #print("m.estimate.hash:  ", m.estimate.hash)
        #print("m.estimate:  ", m.estimate)
        #print("m.sender:  ", m.sender)
        assert m.estimate not in block_to_message, "expected unique blocks"
        block_to_message[m.estimate] = m

    for m in displayable_messages:
        # define edges for prevblock graph
        if m.estimate.prevblock is not None and m.estimate.prevblock in block_to_message:
            PrevblockGraph.add_edge(m, block_to_message[m.estimate.prevblock])

        neighbor_shards = []
        if m.estimate.parent_ID is not None:
            neighbor_shards.append(m.estimate.parent_ID)
        for ID in m.estimate.child_IDs:
            neighbor_shards.append(ID)

        for ID in neighbor_shards:
           # SourcesGraph define edges
            if m.estimate.sources[ID] is not None and m.estimate.sources[ID] in block_to_message:
                SourcesGraph.add_edge(m, block_to_message[m.estimate.sources[ID]])

    # ForkChoiceGraph define edges
    for ID in SHARD_IDS:
        this_block = fork_choice[ID]
        while(this_block.prevblock is not None and this_block.prevblock in block_to_message):
            ForkChoiceGraph.add_edge(block_to_message[this_block], block_to_message[this_block.prevblock])
            this_block = this_block.prevblock

    # Draw edges
    #nx.draw_networkx_edges(SourcesGraph, messagesPos, style='dashdot', edge_color='y', arrowsize=10, width=1)
    nx.draw_networkx_edges(ForkChoiceGraph, messagesPos, edge_color='#bdbdbd', alpha=1, arrowsize=25, width=15)
    nx.draw_networkx_edges(PrevblockGraph, messagesPos, width=3)
    nx.draw_networkx_nodes(PrevblockGraph, messagesPos, node_shape='s', node_color='#3c3c3d', node_size=300)


    # CROSS SHARD MESSAGES
    ShardMessagesGraph = nx.Graph();
    ShardMessagesOriginGraph = nx.Graph();
    shard_messagesPos = {}

    consensus_message_by_shard_message = {}
    for m in displayable_messages:
        ShardMessagesOriginGraph.add_node(m)
        shard_messagesPos[m] = messagesPos[m]

        # Messages to parents are displayed above their sending blocks
        if m.estimate.parent_ID is not None:
            ID = m.estimate.parent_ID
            for shard_message in m.estimate.newly_sent()[ID]:
                assert shard_message not in consensus_message_by_shard_message.keys(), "expected not to overwrite consensus message"
                consensus_message_by_shard_message[shard_message] = m
                ShardMessagesGraph.add_node(shard_message)
                ShardMessagesOriginGraph.add_node(shard_message)
                xoffset = (m.height % 3 - 1)*SHARD_MESSAGE_XOFFSET
                yoffset = SHARD_MESSAGE_YOFFSET
                shard_messagesPos[shard_message] = (messagesPos[m][0] + xoffset, messagesPos[m][1] + yoffset)
                ShardMessagesOriginGraph.add_edge(m, shard_message)

        # Messages to children are displayed below their sending blocks
        for ID in m.estimate.child_IDs:
            for shard_message in m.estimate.newly_sent()[ID]:
                assert shard_message not in consensus_message_by_shard_message.keys(), "expected not to overwrite consensus message"
                consensus_message_by_shard_message[shard_message] = m
                ShardMessagesGraph.add_node(shard_message)
                ShardMessagesOriginGraph.add_node(shard_message)
                yoffset = -SHARD_MESSAGE_YOFFSET
                xoffset = (m.height % 3 - 1)*SHARD_MESSAGE_XOFFSET
                shard_messagesPos[shard_message] = (messagesPos[m][0] + xoffset, messagesPos[m][1] + yoffset)
                ShardMessagesOriginGraph.add_edge(m, shard_message)

    nx.draw_networkx_nodes(ShardMessagesOriginGraph, shard_messagesPos, node_size=0)
    nx.draw_networkx_nodes(ShardMessagesGraph, shard_messagesPos, node_shape='o', node_color='#f6546a', node_size=250)
    nx.draw_networkx_edges(ShardMessagesOriginGraph, shard_messagesPos, width=6, style='dotted')

    # CROSS SHARD MESSAGE RECEIVE ARROWS
    RECEIVED_GRAPH_COLORS = ['#000000', '#600787', '#078760', '#876007', '#870760',
                             '#076087', '#608707', '#FF6633', '#FFB399', '#FF33FF',
                             '#E6B333', '#3366E6', '#999966', '#99FF99', '#B34D4D',
                             '#80B300', '#809900', '#E6B3B3', '#6680B3', '#66991A',
                             '#FF99E6', '#CCFF1A', '#FF1A66', '#E6331A', '#33FFCC',
                             '#66994D', '#B366CC', '#4D8000', '#B33300', '#CC80CC',
                             '#66664D', '#991AFF', '#E666FF', '#4DB3FF', '#1AB399',
                             '#E666B3', '#33991A', '#CC9999', '#B3B31A', '#00E680',
                             '#4D8066', '#809980', '#E6FF80', '#1AFF33', '#999933',
                             '#FF3380', '#CCCC00', '#66E64D', '#4D80CC', '#9900B3',
                             '#E64D66', '#4DB380', '#FF4D4D', '#99E6E6', '#6666FF']

    OrphanedReceivedMessagesGraph = [nx.DiGraph() for _ in RECEIVED_GRAPH_COLORS];
    AcceptedReceivedMessagesGraph = [nx.DiGraph() for _ in RECEIVED_GRAPH_COLORS];

    for m in displayable_messages:
        neighbor_shards = []
        if m.estimate.parent_ID is not None:
            neighbor_shards.append(m.estimate.parent_ID)
        for ID in m.estimate.child_IDs:
            neighbor_shards.append(ID)

        for i in range(len(RECEIVED_GRAPH_COLORS)):
            OrphanedReceivedMessagesGraph[i].add_node(m)
            AcceptedReceivedMessagesGraph[i].add_node(m)

        for ID in neighbor_shards:
            for new_received_message in m.estimate.newly_received()[ID]:

                for i in range(len(RECEIVED_GRAPH_COLORS)):
                    OrphanedReceivedMessagesGraph[i].add_node(new_received_message)
                    AcceptedReceivedMessagesGraph[i].add_node(new_received_message)
                    OrphanedReceivedMessagesGraph[i].add_node(("r", new_received_message))
                    AcceptedReceivedMessagesGraph[i].add_node(("r", new_received_message))

                assert m in shard_messagesPos.keys()
                shard_messagesPos[("r", new_received_message)] = shard_messagesPos[m]

                #  Hypothesis is that this continue only occurs when the source of the new received is outside of the displayable messages
                if new_received_message not in consensus_message_by_shard_message.keys():
                    continue

                new_shard_message_origin = consensus_message_by_shard_message[new_received_message]
                sending_block = new_shard_message_origin.estimate

                COLOR_ID = hash((new_received_message.TTL, new_received_message.payload, new_received_message.target_shard_ID)) % (len(RECEIVED_GRAPH_COLORS) - 1) + 1

                if isinstance(new_received_message, (SwitchMessage_BecomeAParent, SwitchMessage_ChangeParent, SwitchMessage_Orbit)):
                    COLOR_ID = 0
                else: # XXX
                    pass
                    #continue

                if fork_choice[m.estimate.shard_ID].is_in_chain(m.estimate):
                    if fork_choice[sending_block.shard_ID].is_in_chain(sending_block):
                        #print("m.estimate", m.estimate)
                        #print("sending_block", sending_block)
                        #print("fork_choice[m.estimate.shard_ID]", fork_choice[m.estimate.shard_ID])
                        #print("fork_choice[sending_block.shard_ID]", fork_choice[sending_block.shard_ID])
                        AcceptedReceivedMessagesGraph[COLOR_ID].add_edge(new_received_message, ("r", new_received_message))
                        continue

                OrphanedReceivedMessagesGraph[COLOR_ID].add_edge(new_received_message, ("r", new_received_message))

    for i, clr in enumerate(RECEIVED_GRAPH_COLORS):
        nx.draw_networkx_edges(AcceptedReceivedMessagesGraph[i], shard_messagesPos, edge_color=clr, arrowsize=50, arrowstyle='->', width=8)
        nx.draw_networkx_edges(OrphanedReceivedMessagesGraph[i], shard_messagesPos, edge_color=clr, arrowsize=20, arrowstyle='->', width=1.25)

    ax = plt.axes()
    if SWITCH_ROUND - round_number >= 0:
        ax.text(0.1, 0.05, "Switch Countdown: " + str(SWITCH_ROUND - round_number),
        horizontalalignment='center',
        verticalalignment='bottom',
        transform=ax.transAxes,
        size=50)

    ax.text(0.1, 0.00, "Free instant broadcast: " + str(FREE_INSTANT_BROADCAST),
    horizontalalignment='center',
    verticalalignment='bottom',
    transform=ax.transAxes,
    size=50)

    ax.text(0.1, -0.05, "Validating: " + str(not VALIDITY_CHECKS_OFF),
    horizontalalignment='center',
    verticalalignment='bottom',
    transform=ax.transAxes,
    size=50)

    ax.text(0.1, -0.1, "Saving frames: " + str(SAVE_FRAMES),
    horizontalalignment='center',
    verticalalignment='bottom',
    transform=ax.transAxes,
    size=50)


    if SHOW_FRAMES:
        plt.axis('off')
        plt.draw()
        plt.pause(PAUSE_LENGTH)

    if SAVE_FRAMES:
        print('./graphs/' + str(10000000 + round_number) + ".png")
        plt.savefig('./graphs/' + str(10000000 + round_number) + ".png")


IMAGE_LIMIT = 219
class PlotTool(object):
    """A base object with functions for building, displaying, and saving viewgraphs"""

    def __init__(self):
        self.graph_path = os.path.dirname(os.path.abspath(__file__)) + '/graphs/'
        self.thumbnail_path = os.path.dirname(os.path.abspath(__file__)) + '/thumbnails/'


    def make_thumbnails(self, frame_count_limit=IMAGE_LIMIT, xsize=1000, ysize=1000):
        """Make thumbnail images in PNG format."""

        file_names = sorted([fn for fn in os.listdir(self.graph_path) if fn.endswith('.png')])
        print("len(file_names)", len(file_names))

        if len(file_names) > frame_count_limit:
            raise Exception("Too many frames!")

        images = []
        for file_name in file_names:
            images.append(Image.open(self.graph_path + file_name))


        size = (xsize, ysize)
        iterator = 0
        for image in images:
            image.thumbnail(size)#, Image.ANTIALIAS)
            image.save(self.thumbnail_path + str(1000 + iterator) + "thumbnail.png", "PNG")
            iterator += 1


    def make_gif(self, frame_count_limit=IMAGE_LIMIT, gif_name="mygif.gif", frame_duration=0.4):
        """Make a GIF visualization of view graph."""

        self.make_thumbnails(frame_count_limit=frame_count_limit)

        file_names = sorted([file_name for file_name in os.listdir(self.thumbnail_path)
                             if file_name.endswith('thumbnail.png')])

        images = []
        for file_name in file_names:
            images.append(Image.open(self.thumbnail_path + file_name))

        destination_filename = self.graph_path + gif_name

        iterator = 0
        with io.get_writer(destination_filename, mode='I', duration=frame_duration) as writer:
            for file_name in file_names:
                image = io.imread(self.thumbnail_path + file_name)
                writer.append_data(image)
                iterator += 1

        writer.close()


'''
    ax = plt.axes()
    # FLOATING TEXT
    for ID in SHARD_IDS:
        ax.text(ShardBorderPos[(ID,"bottomleft")][0], ShardBorderPos[(ID,"bottomleft")][1], ID,
        horizontalalignment='right',
        verticalalignment='center',
        size=25)

    plt.axis('off')
    plt.draw()
    plt.pause(PAUSE_LENGTH)
'''
