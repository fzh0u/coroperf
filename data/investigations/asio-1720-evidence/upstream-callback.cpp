#include <functional>
#include <future>
#include <utility>
#include <boost/asio.hpp>
#include <iostream>
int main()
{
    using namespace boost::asio;

    thread_pool         pool{1};
    const ip::address   myAddress{ip::make_address("127.0.0.1")};
    const ip::port_type myPort{54'321};

    ip::tcp::acceptor acceptor(pool.get_executor(), ip::tcp::endpoint{myAddress, myPort});

    ip::tcp::socket socket{pool.get_executor()};
    socket.connect(ip::tcp::endpoint{myAddress, myPort});

    auto acceptedSock = acceptor.async_accept(use_future).get();

    socket.close();
    
    // Control: one outstanding write at a time, using a completion handler.
    const std::string msg{"hello\n"};
    std::promise<void> finished;
    auto future = finished.get_future();
    int attempt = 0;
    std::function<void()> send_next;
    send_next = [&] {
        std::cout << "Try: " << attempt++ << '\n';
        acceptedSock.async_write_some(buffer(msg),
            [&](boost::system::error_code ec, std::size_t) {
                if (ec) std::cout << "Write error: " << ec << '\n';
                if (attempt < 10) send_next();
                else finished.set_value();
            });
    };
    post(pool, send_next);
    const bool done = future.wait_for(std::chrono::seconds(3)) == std::future_status::ready;
    pool.stop();
    pool.join();
    return done ? 0 : 2;
}