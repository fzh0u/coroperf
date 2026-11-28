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
    
    const auto writeFunc{[](ip::tcp::socket& sock) -> awaitable<void> {
        const std::string message{"hello\n"};
        constexpr auto    retries{10};
        for(auto i{0}; i < retries; ++i) {
            std::cout << "Try: " << i << "\n";
            try {
                co_await sock.async_write_some(buffer(message), use_awaitable);
            } catch(const boost::system::system_error& e) {
                std::cout << "Write exception: " << e.code() << '\n';
            }
        }
    }};

    auto future = co_spawn(pool.get_executor(), writeFunc(acceptedSock), use_future);

    return future.wait_for(std::chrono::seconds(3)) == std::future_status::ready ? 0 : 2;
}
