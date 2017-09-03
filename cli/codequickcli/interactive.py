# Standard Library Imports
from multiprocessing import Process, Pipe
import re

# Package imports
from codequickcli import support, initialize_addon
from codequickcli.addondb import db as addon_db
from codequickcli.support import urlparse, input_raw


def interactive(pluginid, preselect=None):
    """
    Execute a given kodi plugin

    :param str pluginid: The add-on id
    :param list preselect: A list of pre selection to make.
    """
    # TODO: Add support for content_type when plugins have muilti providers e.g. video, music.

    if pluginid.startswith("plugin://"):
        addon_info = addon_db[urlparse.urlsplit(pluginid).hostname]
        callback_url = pluginid
    else:
        addon_info = addon_db[pluginid]
        callback_url = "plugin://%s/" % addon_info.id

    # Keep track of parents so we can have a '..' option
    parent_stack = []

    while callback_url is not None:
        # Execute the addon in a separate process
        data = execute_addon(callback_url, entry_point=addon_info.entry_point)
        if data["succeeded"] is False:
            print("Failed to execute addon. Please check log.")
            try:
                input_raw("Press enter to continue:")
            except KeyboardInterrupt:
                break

            # Revert back to previous callback if one exists
            if parent_stack:
                callback_url = parent_stack.pop()
                continue
            else:
                break

        # Item list with first item as the previous directory item
        items = [{"label": "..", "path": parent_stack[-1]}] if parent_stack else []

        # Display listitem selection if listitems are found
        if data["listitem"]:
            items.extend(item[1] for item in data["listitem"])
        elif data["resolved"]:
            items.append(data["resolved"])
            items.extend(data["playlist"][1:])

        # Display the list of listitems for user to select
        selected_item = item_selector(items, callback_url, preselect)
        if selected_item:
            if parent_stack and selected_item["path"] == parent_stack[-1]:
                callback_url = parent_stack.pop()
            else:
                parent_stack.append(callback_url)
                callback_url = selected_item["path"]
        else:
            break


def execute_addon(callback_url, entry_point):
    """
    Executes a add-on in a separate process.

    :param str callback_url: The url containing the route path and callback params.
    :param str entry_point: The entry point of the addon e.g. addon.py, default.py.
    :returns: A dictionary of listitems and other related results.
    :rtype: dict
    """
    # The interactive mode will only work with addons that have an entry point e.g. addon.py
    if entry_point is None:
        raise RuntimeError("No emtry point specified, An addon entry point must exist within the addon.xml")

    # Pips to handle passing of data from addon process to controler
    pipe_recv, pipe_send = Pipe(duplex=True)

    # Create the new process that will execute the addon
    p = Process(target=subprocess, args=[pipe_send, callback_url, entry_point])
    p.start()

    # Wait till we receive data from the addon process
    while True:
        data = pipe_recv.recv()
        if "prompt" in data:
            input_data = input_raw(data["prompt"])
            pipe_recv.send(input_data)
        else:
            break

    p.join()
    return data


def subprocess(pipe_send, callback_url, entry_point):
    """
    Imports and executes the addon

    :param pipe_send: The communication object used for sending data back to the initiator.
    :param str callback_url: The url containing the route path and callback params.
    :param str entry_point: The entry point of the addon e.g. addon.py, default.py.
    """
    initialize_addon(callback_url)
    support.data_pipe = pipe_send

    try:
        addon = __import__(entry_point)
        addon.run()
    finally:
        # Send back the results from the addon
        pipe_send.send(support.plugin_data)


def item_selector(listitems, current, preselect):
    """
    Displays a list of items along with the index to enable a user to select an item.

    :param list listitems: List of dictionarys containing all of the listitem data.
    :param current: The current callback url.
    :param list preselect: A list of pre selection to make.
    :returns: The selected item
    :rtype: dict
    """
    # Calculate the max length of required lines
    title_len = max(len(item["label"].strip()) for item in listitems) + 1
    num_len = len(str(len(listitems)-1))
    line_width = 400
    type_len = 8

    # Create output list with headers
    output = ["",
              "=" * line_width,
              "Current URL: %s" % current,
              "-" * line_width,
              "%s %s %s Listitem" % ("#".center(num_len+1), "Label".ljust(title_len), "Type".ljust(type_len)),
              "-" * line_width]

    # Create a line output for each listitem entry
    for count, item in enumerate(listitems):
        label = re.sub("\[[^\]]+?\]", "", item.pop("label")).strip()

        if item["path"].startswith("plugin://"):
            if item.get("properties", {}).get("isplayable") == "true":
                item_type = "video"
            elif label == ".." or item.get("properties", {}).get("folder") == "true":
                item_type = "folder"
            else:
                item_type = "script"
        else:
            item_type = "playable"

        line = "%s. %s %s %s" % (str(count).rjust(num_len), label.ljust(title_len), item_type.ljust(type_len), item)
        output.append(line)

    output.append("-" * line_width)
    print("\n".join(output))

    # Return preselected item or ask user to selection
    if preselect:
        print("Item %s has been pre-selected.\n" % preselect[0])
        return listitems[preselect.pop(0)]
    else:
        return user_choice(listitems)


def user_choice(items):
    """
    Returns the selected item from provided items or None if nothing was selected.

    :param list items: List of items to choice from
    :returns: The selected item
    :rtype: dict
    """
    prompt = "Choose an item: "
    while True:
        try:
            # Ask user for selection, Returning None if user entered nothing
            choice = input_raw(prompt)
            if not choice:
                return None

            # Convert choice to an integer and reutrn the selected item
            choice = int(choice)
            item = items[choice]

            # Return the item if it's a plugin path
            if item["path"].startswith("plugin://"):
                print("")
                return item
            else:
                prompt = "Selection is not a valid plugin path, Please choose again: "

        except ValueError:
            prompt = "You entered a non-integer, Choice must be an integer: "
        except IndexError:
            prompt = "You entered an invalid integer, Choice must be from above list: "
        except (EOFError, KeyboardInterrupt):
            # User skipped the prompt
            return None
