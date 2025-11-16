import ast
from typing import Counter
import rules as  R
from datetime import datetime, timedelta

def is_in_specified_channels(message, channels):
    if message.channel.id not in channels:
        return False
    return True

def is_in_specified_forums(message, forums):
    if "thread" not in message.channel.type.name:
        return False
    if message.channel.parent_id not in forums:
        return False
    return True

def is_in_specified_categories(message, categories):
    if message.channel.category_id == None or message.channel.category_id not in categories:
        return False
    return True

def has_specified_role(message, roles):
    for role_id in roles:
        role = message.guild.get_role(role_id)
        if role in message.author.roles:
            return True
    return False

def eval_node(node, context, message):
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(eval_node(v, context, message) for v in node.values)
        elif isinstance(node.op, ast.Or):
            return any(eval_node(v, context, message) for v in node.values)
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not eval_node(node.operand, context, message)
    elif isinstance(node, ast.Name):
        name = node.id.lower()
        data = context["rules"][name]
        match data["type"]:
            case "is_in_specified_channels":
                return R.is_in_specified_channels(message, data["channels"])
            case "is_in_specified_forums":
                return R.is_in_specified_forums(message, data["forums"])
            case "is_in_specified_categories":
                return R.is_in_specified_categories(message, data["categories"])
            case "has_specified_role":
                return R.has_specified_role(message, data["roles"])
            case "request_count":
                return R.request_count(context, message)
            case _:
                raise ValueError(f"Unknown variable '{name}' in expression.")
    else:
        raise ValueError(f"Unsupported expression: {ast.dump(node)}")


def evaluate_expression(context, message):
    """
    Evaluate a logical expression string like:
        ((channels AND forums) OR categories)
    where each variable corresponds to a function call in R.
    """
    expr_str = context["rules"]["rule_expression"]
    # Normalize to Python boolean syntax
    expr_str = expr_str.replace("AND", "and").replace("OR", "or").replace("NOT", "not")

    # Parse safely into an AST
    tree = ast.parse(expr_str, mode="eval")

    return eval_node(tree.body, context, message)


def request_count(context, message):
    
    user_id = message.author.id
    message_time = message.created_at
    max_per_user = context["max_per_user"]
    max_users = context["max_users"]
    counter = context.setdefault("message_counter", {})
    delete_after = timedelta(hours=context["delete_after_hours"])

    # Add the user to the counter if not yet present, as long as we haven't reached max_users in which case delete the oldest user
    if user_id not in counter:
        if len(counter) >= max_users:
            oldest_user = next(iter(counter))
            del counter[oldest_user]

        counter[user_id] = [message_time]
        return True

    # Clean up timestamps older than delete_after
    timestamps = counter[user_id]
    timestamps = [t for t in timestamps if message_time - t < delete_after]
    counter[user_id] = timestamps

    # If the user has free slots, add the current timestamp and allow the request
    if len(timestamps) < max_per_user:
        counter[user_id].append(message_time)
        return True

    return False