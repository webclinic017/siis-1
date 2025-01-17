/**
 * @date 2020-01-24
 * @author Frederic Scherma, All rights reserved without prejudices.
 * @license Copyright (c) 2020 Dream Overflow
 * Web trader alerts handler.
 */

// @todo add price cross alert dialog

function on_strategy_signal_alert(market_id, alert_id, timestamp, alert, do_notify=true) {
    let alert_elt = $('<tr class="alert"></tr>');
    let key = market_id + ':' + alert.id;
    alert_elt.attr('alert-key', key);

    let symbol = window.markets[market_id] ? window.markets[market_id]['symbol'] : market_id;

    let lalert_id = $('<span class="alert-id"></span>').text(alert.id);
    let alert_symbol = $('<span class="alert-symbol badge badge-info"></span>').text(symbol).attr('title', market_id);
    let alert_direction = $('<span class="alert-direction fa"></span>')
        .addClass(alert.trigger > 0 ? 'trade-long' : 'trade-short')
        .addClass(alert.trigger > 0 ? 'fa-arrow-up' : 'fa-arrow-down');

    let alert_label = $('<span class="alert-label"></span>').text(alert.name);
    // in seconds timestamp
    let alert_datetime = $('<span class="alert-datetime"></span>').text(timestamp_to_datetime_str(alert.timestamp));

    // timeframe is formatted
    let timeframe = alert.timeframe == 't' ? "trade/tick" : alert.timeframe;

    let alert_timeframe = $('<span class="alert-timeframe"></span>').text(timeframe);
    let alert_lastprice = $('<span class="alert-last-price"></span>').text(alert['last-price']);
    let alert_reason = $('<span class="alert-reason"></span>').text(alert.reason);

    let alert_message = $('<span class="alert-message"></span>').text(alert.message);
    let alert_details = $('<button class="alert-details btn btn-info fas fa-info"></button>');

    alert_elt.append($('<td></td>').append(lalert_id));
    alert_elt.append($('<td></td>').append(alert_symbol));
    alert_elt.append($('<td></td>').addClass('optional-info').append(alert_label));
    alert_elt.append($('<td></td>').append(alert_direction));
    alert_elt.append($('<td></td>').append(alert_timeframe));
    alert_elt.append($('<td></td>').addClass('optional-info').append(alert_lastprice));
    alert_elt.append($('<td></td>').append(alert_reason));
    alert_elt.append($('<td></td>').addClass('optional-info').append(alert_message));
    alert_elt.append($('<td></td>').append(alert_datetime));

    alert_elt.append($('<td></td>').append(alert_details));

    // actions
    alert_details.on('click', on_details_signal_alert);

    // append
    $('div.alert-list-entries tbody').prepend(alert_elt);

    if (do_notify) {
        let message = alert.name + " "  + alert.reason + " " + alert.symbol + " " + alert.message;
        notify({'message': message, 'title': 'Strategy Alert', 'type': 'info'});
        audio_notify('alert');
    }

    window.alerts[key] = alert;

    // cleanup above 200 alerts
    if (Object.keys(window.alerts).length > 200) {
        for (alert_key in window.alerts) {
            // @todo remove and update view
        }
    }
}

function price_src_to_str(price_src) {
    switch (price_src) {
        case 0:
            return "bid";
        case 1:
            return "ask";
        case 2:
            return "mid";
        default:
            return "";
    }
}

function alert_name_format(alert_data, market_id, price_src) {
    let condition_msg = "-";

    if (alert_data.name == "price-cross") {
        if (alert_data.direction > 0) {
            condition_msg = `if ${price_src} price goes above ${format_price(market_id, alert_data.price)}`;
        } else if (alert.direction < 0) {
            condition_msg = `if ${price_src} price goes below ${format_price(market_id, alert_data.price)}`;
        }
    }

    return condition_msg;
}

function alert_cancellation_format(alert_data, market_id, price_src) {
    let cancellation_msg = "never";

    if (alert_data.cancellation > 0) {
        if (alert_data.direction > 0) {
            cancellation_msg = `if ${price_src} price < ${format_price(market_id, alert_data.cancellation)}`;
        } else if (alert.direction < 0) {
            cancellation_msg = `if ${price_src} price > ${format_price(market_id, alert_data.cancellation)}`;
        }
    }

    return cancellation_msg;
}

function on_strategy_create_alert(market_id, alert_id, timestamp, alert, do_notify=true) {
    let key = market_id + ':' + alert_id;

    let alert_elt = $('<tr class="active-alert"></tr>');
    alert_elt.attr('active-alert-key', key);

    let condition_msg = "-";
    let cancellation_msg = "never";

    let price_src = price_src_to_str(alert['price-src']);

    condition_msg = alert_name_format(alert, market_id, price_src);
    cancellation_msg = alert_cancellation_format(alert, market_id, price_src);

    let symbol = window.markets[market_id] ? window.markets[market_id]['symbol'] : market_id;

    let lalert_id = $('<span class="alert-id"></span>').text(alert.id);
    let alert_symbol = $('<span class="alert-symbol badge badge-info"></span>').text(symbol).attr('title', market_id);

    let alert_label = $('<span class="alert-label"></span>').text(alert.name);
    let alert_datetime = $('<span class="alert-datetime"></span>').text(timestamp_to_datetime_str(alert.created));

    // timeframe is not formatted
    let alert_timeframe = $('<span class="alert-timeframe"></span>').text(alert.timeframe || "trade/tick");
    let alert_expiry = $('<span class="alert-expiry"></span>');
    if (alert.expiry > 0) {
        // absolute timestamp
        alert_expiry.text(timestamp_to_datetime_str(alert.expiry));
    } else {
        alert_expiry.text("never");
    }

    let alert_condition = $('<span class="alert-condition"></span>').text(condition_msg);
    let alert_countdown = $('<span class="alert-countdown"></span>').text(alert.countdown);
    let alert_cancellation = $('<span class="alert-cancellation"></span>').text(cancellation_msg);
    let alert_message = $('<span class="alert-message"></span>').text(alert.message);

    alert_elt.append($('<td></td>').append(lalert_id));
    alert_elt.append($('<td></td>').append(alert_symbol));
    alert_elt.append($('<td></td>').addClass('optional-info').append(alert_label));
    alert_elt.append($('<td></td>').append(alert_timeframe));
    alert_elt.append($('<td></td>').addClass('optional-info').append(alert_expiry));
    alert_elt.append($('<td></td>').addClass('optional-info').append(alert_countdown));
    alert_elt.append($('<td></td>').append(alert_condition));
    alert_elt.append($('<td></td>').addClass('optional-info').append(alert_cancellation));
    alert_elt.append($('<td></td>').append(alert_message));

    // actions
    let alert_remove = $('<button class="alert-remove btn btn-danger fas fa-window-close"></button>');

    if (server.permissions.indexOf("strategy-trader") < 0) {
        alert_remove.attr("disabled", "")
    }

    alert_elt.append($('<td></td>').append(alert_remove));

    let alert_details = $('<button class="alert-details btn btn-info fas fa-info"></button>');
    alert_elt.append($('<td></td>').append(alert_details));

    alert_details.on('click', on_details_alert);

    // append
    $('div.active-alert-list-entries tbody').prepend(alert_elt);

    // actions
    if (server.permissions.indexOf("strategy-trader") != -1) {
        alert_remove.on('click', on_remove_alert);
    }

    if (do_notify) {
        let message = alert.name + " "  + condition_msg + " " + alert.symbol + " " + alert.message;
        notify({'message': message, 'title': 'Strategy Alert Created', 'type': 'info'});
    }

    window.active_alerts[key] = alert;
}

function on_remove_alert(elt) {
    let key = retrieve_alert_key(elt);

    let parts = key.split(':');
    if (parts.length != 2) {
        return false;
    }

    let market_id = parts[0];
    let alert_id = parseInt(parts[1]);

    let endpoint = "strategy/alert";
    let url = base_url() + '/' + endpoint;

    let market = window.markets[market_id];

    if (market_id && market && alert_id) {
        let data = {
            'market-id': market['market-id'],
            'alert-id': alert_id,
            'action': "del-alert"
        };

        $.ajax({
            type: "DELETE",
            url: url,
            headers: {
                'Authorization': "Bearer " + server['auth-token'],
                'TWISTED_SESSION': server.session,
            },
            data: JSON.stringify(data),
            dataType: 'json',
            contentType: 'application/json'
        })
        .done(function(data) {
            if (data.error) {
                for (let msg in data.messages) {
                    notify({'message': data.messages[msg], 'title': 'Remove Alert', 'type': 'error'});
                }
            } else {
                notify({'message': "Success", 'title': 'Remove Alert', 'type': 'success'});
            }
        })
        .fail(function(data) {
            for (let msg in data.messages) {
                notify({'message': msg, 'title': 'Remove Alert', 'type': 'error'});
            }
        });
    }
}

function on_strategy_remove_alert(market_id, timestamp, alert_id) {
    let key = market_id + ':' + alert_id;
    let container = $('div.active-alert-list-entries tbody');

    container.find('tr.active-alert[active-alert-key="' + key + '"]').remove();
    if (key in window.active_alerts) {
        delete window.active_alerts[key];
    }
}

window.fetch_alerts = function() {
    // fetch actives alerts
    let endpoint1 = "strategy/alert";
    let url1 = base_url() + '/' + endpoint1;

    let params1 = {}

    $.ajax({
        type: "GET",
        url: url1,
        data: params1,
        headers: {
            'TWISTED_SESSION': server.session,
            'Authorization': "Bearer " + server['auth-token'],
        },
        dataType: 'json',
        contentType: 'application/json'
    })
    .done(function(result) {
        window.active_alerts = {};

        let alerts = result['data'];
        if (!alerts) {
            return;
        }

        // naturally ordered
        for (let i = 0; i < alerts.length; ++i) {
            let alert = alerts[i];

            window.active_alerts[alert['market-id'] + ':' + alert.id] = alert;

            // initial add
            on_strategy_create_alert(alert['market-id'], alert.id, alert.timestamp, alert, false);
        }
    })
    .fail(function() {
        notify({'message': "Unable to obtains actives alerts !", 'title': 'fetching"', 'type': 'error'});
    });

    // fetch last history of alerts
    let endpoint2 = "strategy/historical-alert";
    let url2 = base_url() + '/' + endpoint2;

    let params2 = {}

    $.ajax({
        type: "GET",
        url: url2,
        data: params2,
        headers: {
            'TWISTED_SESSION': server.session,
            'Authorization': "Bearer " + server['auth-token'],
        },
        dataType: 'json',
        contentType: 'application/json'
    })
    .done(function(result) {
        window.alerts = {};

        let alerts = result['data'];
        if (!alerts) {
            return;
        }

        // naturally ordered
        for (let i = 0; i < alerts.length; ++i) {
            let alert = alerts[i];

            window.alerts[alert['market-id'] + ':' + alert.id] = alert;

            // initial add
            on_strategy_signal_alert(alert['market-id'], alert.id, alert.timestamp, alert, false);
        }
    })
    .fail(function() {
        notify({'message': "Unable to obtains historical alerts !", 'title': 'fetching"', 'type': 'error'});
    });
};

function on_add_price_cross_alert(elt) {
    alert("TODO");
}

function on_details_signal_alert(elt) {
    let key = retrieve_alert_key(elt);
    let table = $('#alert_details_table');
    let tbody = table.find('tbody').empty();

    let alert_signal = window.alerts[key];
    if (!alert_signal) {
        return;
    }

    let market_id = region['market-id'];

    $('#alert_details').modal({'show': true, 'backdrop': true});
}

function on_details_alert(elt) {
    let key = retrieve_alert_key(elt);
    let table = $('#active_alert_details_table');
    let tbody = table.find('tbody').empty();

    let active_alert = window.active_alerts[key];
    if (!active_alert) {
        return;
    }

    let market_id = active_alert['market-id'];
    let price_src = price_src_to_str(alert['price-src']);

    let condition_msg = alert_name_format(active_alert, market_id, price_src);
    let cancellation_msg = alert_cancellation_format(active_alert, market_id, price_src);

    let id = $('<tr></tr>').append($('<td class="data-name">Identifier</td>')).append(
        $('<td class="data-value">' + active_alert.id + '</td>'));
    let lmarket_id = $('<tr></tr>').append($('<td class="data-name">Market</td>')).append(
        $('<td class="data-value"><span class="badge badge-info">' + active_alert['market-id'] + '</span></td>'));
    let symbol = $('<tr></tr>').append($('<td class="data-name">Symbol</td>')).append(
        $('<td class="data-value"><span class="badge badge-info">' + active_alert.symbol + '</span></td>'));
    let version = $('<tr></tr>').append($('<td class="data-name">Version</td>')).append(
        $('<td class="data-value">' + active_alert.version + '</td>'));
    let timestamp = $('<tr></tr>').append($('<td class="data-name">Created</td>')).append(
        $('<td class="data-value">' + timestamp_to_datetime_str(active_alert.created) + '</td>'));
    let timeframe = $('<tr></tr>').append($('<td class="data-name">Timeframe</td>')).append(
        $('<td class="data-value">' + (timeframe_to_str(active_alert.timeframe) || "trade/tick") + '</td>'));
    let expiry = $('<tr></tr>').append($('<td class="data-name">Expiry</td>')).append(
        $('<td class="data-value">' + (timeframe_to_str(active_alert.expiry) || "never") + '</td>'));

    let label = $('<tr></tr>').append($('<td class="data-name">Label</td>')).append(
        $('<td class="data-value">' + active_alert.name + '</td>'));
    let alert_price = $('<tr></tr>').append($('<td class="data-name">Price</td>')).append(
        $('<td class="data-value">' + format_price(market_id, active_alert.price) + '</td>'));

    let spacer1 = $('<tr></tr>').append($('<td class="data-name">-</td>')).append(
        $('<td class="data-value">-</td>'));

    let condition = $('<tr></tr>').append($('<td class="data-name">Trigger condition</td>')).append(
        $('<td class="data-value">' + condition_msg + '</td>'));

    let spacer2 = $('<tr></tr>').append($('<td class="data-name">-</td>')).append(
        $('<td class="data-value">-</td>'));

    let direction = $('<tr></tr>').append($('<td class="data-name">Direction</td>')).append(
        $('<td class="data-value">' + active_alert.direction + '</td>'));
    if (active_alert.direction == "long" || active_alert.direction == 1) {
        direction = $('<tr></tr>').append($('<td class="data-name">Direction</td>')).append(
        $('<td class="data-value"><span class="alert-direction fas alert-up fa-arrow-up"></span></td>'));
    } else if (active_alert.direction == "short" || active_alert.direction == -1) {
        direction = $('<tr></tr>').append($('<td class="data-name">Direction</td>')).append(
        $('<td class="data-value"><span class="alert-direction fas alert-down fa-arrow-dn"></span></td>'));
    }

    let cancellation_price_rate = compute_price_pct(active_alert['cancellation-price'],
        active_alert.price,
        active_alert.direction == "long" || active_alert.direction == 1 ? 1 : -1);
    let cancellation_price_pct = (cancellation_price_rate * 100).toFixed(2) + '%';
    let cancellation_price = $('<tr></tr>').append($('<td class="data-name">Cancellation-Price</td>')).append(
        $('<td class="data-value">' + format_price(market_id, active_alert['cancellation-price']) + ' (' +
        cancellation_price_pct + ')</td>'));

    let spacer3 = $('<tr></tr>').append($('<td class="data-name">-</td>')).append(
        $('<td class="data-value">-</td>'));

    let cancellation_condition = $('<tr></tr>').append($('<td class="data-name">Cancellation condition</td>')).append(
        $('<td class="data-value">' + cancellation_msg + '</td>'));

    let spacer4 = $('<tr></tr>').append($('<td class="data-name">-</td>')).append(
        $('<td class="data-value">-</td>'));

    let comment = $('<tr></tr>').append($('<td class="data-name">User comment</td>')).append(
        $('<td class="data-value">' + (active_alert.message || '-') + '</td>'));

    tbody.append(id);
    tbody.append(lmarket_id);
    tbody.append(symbol);
    tbody.append(version);
    tbody.append(timestamp);
    tbody.append(timeframe);
    tbody.append(expiry);
    tbody.append(direction);
    tbody.append(label);
    tbody.append(alert_price);
    tbody.append(spacer1);
    tbody.append(condition);
    tbody.append(spacer2);
    tbody.append(cancellation_price);
    tbody.append(spacer3);
    tbody.append(cancellation_condition);
    tbody.append(spacer4);
    tbody.append(comment);

    $('#active_alert_details').modal({'show': true, 'backdrop': true});
}
