package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"math"
	"math/rand"
	"net"
	"regexp"
	"strconv"
	"strings"
	"syscall"
	"time"
)

const ReplyBusy = "BUSY\n"
const ReplySendOK = "SEND-OK\n"
const ReplyUnknown = "BAD-DEST-USER\n"
const ReplyBadHdr = "BAD-RQST-HDR\n"
const ReplyBadBody = "BAD-RQST-BODY\n"
const ReplyInUse = "IN-USE\n"
const ReplySetOK = "SET-OK\n"
const timeout = 5 * time.Minute

const maxDelay = 30 * time.Second
const maxBurst = 1024

var (
	regexName                     = regexp.MustCompile("((HELLO-FROM) (\\p{L}0-9]+)$)")
	regexSend                     = regexp.MustCompile("((SEND) (\\p{L}+) ([^\n]+)$)")
	regexGet                      = regexp.MustCompile("((GET) ([\\p{L}\\-]+)$)")
	regexSet                      = regexp.MustCompile("((SET) (\\p{L}+) (([0-9]*[.])?[0-9]+)$)")
	regexSetRange                 = regexp.MustCompile("((SET) ([\\p{L}\\-]+) ([0-9]+) ([0-9]+)$)")
	regexReset                    = regexp.MustCompile("(RESET)")
)

type Settings struct {
	drop          float64
	flip          float64
	burst         float64
	burstLenLower int64
	burstLenUpper int64
	delay         float64
	delayLenLower int64
	delayLenUpper int64
}

type LocalSettings struct {
	drop          float64
	flip          float64
	burst         float64
	delay         float64
	burstLenLower int64
	burstLenUpper int64
	delayLenLower int64
	delayLenUpper int64
	maxClients    int64
}

type ClientBookkeeping struct {
	addrToName     map[string]string
	nameToAddr     map[string]string
	addrToTime     map[string]time.Time
	addrToSettings map[string]*Settings
}

func (cb *ClientBookkeeping) Add(addr net.Addr, name string) {
	newSet := new(Settings)
	cb.nameToAddr[name] = addr.String()
	cb.addrToName[addr.String()] = name
	cb.addrToTime[addr.String()] = time.Now()
	cb.addrToSettings[addr.String()] = newSet

}

func (cb *ClientBookkeeping) IsKnown(user string) bool {
	_, ok := cb.nameToAddr[user]
	return ok
}

func (cb *ClientBookkeeping) ping(addr net.Addr) {
	cb.addrToTime[addr.String()] = time.Now()
}

func (cb *ClientBookkeeping) IsFull() bool {
	return len(cb.addrToName) >= int(localSettings.maxClients)
}

func (cb *ClientBookkeeping) GetUser(addr net.Addr) (string, bool) {
	v, b := cb.addrToName[addr.String()]
	if b {
		cb.ping(addr)
	}
	return v, b
}

func (cb *ClientBookkeeping) GetAddress(name string) (string, bool) {
	v, b := cb.nameToAddr[name]
	return v, b
}

func (cb *ClientBookkeeping) Clean() {
	now := time.Now()
	for k, v := range cb.addrToTime {
		if now.Sub(v) > timeout {
			if name, ok := cb.addrToName[k]; ok {
				delete(cb.nameToAddr, name)
			}
			delete(cb.addrToName, k)
			delete(cb.addrToTime, k)
			delete(cb.addrToSettings, k)
		}
	}
}

func (cb *ClientBookkeeping) GetNames() string {
	var b strings.Builder
	first := true
	for k := range cb.nameToAddr {
		if first {
			first = false
		} else {
			b.WriteByte(',')
		}
		b.WriteString(k)
	}
	return b.String()
}

var cb = ClientBookkeeping{make(map[string]string), make(map[string]string), make(map[string]time.Time), make(map[string]*Settings)}
var localSettings LocalSettings

type BrokenMessageOutputStream struct {
	conn net.PacketConn
}

func (b *BrokenMessageOutputStream) Send(addr net.Addr, msg string) {
	special := strings.HasPrefix(msg, "SET-OK") || strings.HasPrefix(msg, "VALUE")
	if !special {
		if rand.Float64() < localSettings.drop {
			return
		}
		msgBytes := []byte(msg)
		msgBytes = addBitFlips(msgBytes, localSettings.flip)
		if rand.Float64() < localSettings.burst {
			burstLen := localSettings.burstLenLower
			if burstRange := localSettings.burstLenUpper - localSettings.burstLenLower; burstRange > 0 {
				burstLen += rand.Int63n(burstRange)
			}
			msgBytes = addBurstError(msgBytes, burstLen)
		}
		if rand.Float64() < localSettings.delay {
			delay := time.Second * time.Duration(localSettings.delayLenLower)
			if delayRange := localSettings.delayLenUpper - localSettings.delayLenLower; delayRange > 0 {
				delay += time.Second * time.Duration(rand.Int63n(delayRange))
			}
			go func() {
				time.Sleep(delay)
				b.WriteAndLog(msgBytes, addr)
			}()
		} else {
			b.WriteAndLog(msgBytes, addr)
		}
	} else {
		b.WriteAndLog([]byte(msg), addr)
	}
}

func addBurstError(bytes []byte, burstLen int64) []byte {
	var sb strings.Builder
	for _, b := range bytes {
		sb.WriteString(fmt.Sprintf("%08b", b))
	}
	var sb2 strings.Builder
	offset := 0
	maxOffset := 8*len(bytes) - int(burstLen)
	if maxOffset > 0 {
		offset = rand.Intn(maxOffset)
	}
	v := "10"[rand.Intn(2)]
	for _, char := range sb.String() {
		if offset <= 0 && burstLen > 0 {
			sb2.WriteRune(rune(v))
			burstLen -= 1
		} else {
			sb2.WriteRune(char)
		}
		if offset > 0 {
			offset -= 1
		}
	}
	binaryString := sb2.String()
	res := make([]byte, len(bytes))
	for i := 0; i < len(bytes); i++ {
		val, err := strconv.ParseUint(binaryString[i*8:i*8+8], 2, 8)
		if err != nil {
			log.Panic(err)
		}
		res[i] = byte(val)
	}
	return res
}

func addBitFlips(bytes []byte, flip float64) []byte {
	var sb strings.Builder
	for _, b := range bytes {
		sb.WriteString(fmt.Sprintf("%08b", b))
	}
	var sb2 strings.Builder
	for _, char := range sb.String() {
		if rand.Float64() < flip {
			switch char {
			case '1':
				sb2.WriteRune('0')
			case '0':
				sb2.WriteRune('1')
			}
		} else {
			sb2.WriteRune(char)
		}
	}
	binaryString := sb2.String()
	res := make([]byte, len(bytes))
	for i := 0; i < len(bytes); i++ {
		val, err := strconv.ParseUint(binaryString[i*8:i*8+8], 2, 8)
		if err != nil {
			log.Panic(err)
		}
		res[i] = byte(val)
	}
	return res
}

func (b *BrokenMessageOutputStream) WriteAndLog(msg []byte, addr net.Addr) {
	log.Printf("TO %v: %v\n", addr.String(), string(msg))
	_, _ = b.conn.WriteTo(msg, addr)
}

func main() {
	address := flag.String("address", "127.0.0.1", "The Chat Server Address.")
	port := flag.String("port", "5382", "The Chat Server Port.")

	burst := flag.Float64("burst", 0, "The probability of message burst. Works only if executed locally")
	delay := flag.Float64("delay", 0, "Message delay. Works only if executed locally")
	flip := flag.Float64("flip", 0, "The probability of flipping a bit. Works only if executed locally")
	drop := flag.Float64("drop", 0, "The probability of dropping a message. Works only if executed locally")
	burstLenLower := flag.Int64("burstLenLower", 0, "The lower burst length")
	burstLenUpper := flag.Int64("burstLenUpper", 0, "The upper burst length")
	delayLenLower := flag.Int64("delayLenLower", 0, "The lower delay length")
	delayLenUpper := flag.Int64("delayLenUpper", 0, "The upper delay length")
	maxClientsPtr := flag.Int64("maxClients", 1000, "Max number of clients")

	flag.Parse()

	localSettings.burst = math.Max(0, math.Min(*burst, 1))
	localSettings.delay = math.Max(0, math.Min(*delay, 1))
	localSettings.flip = math.Max(0, math.Min(*flip, 1))
	localSettings.drop = math.Max(0, math.Min(*drop, 1))

	localSettings.burstLenLower = int64(math.Max(0, float64(*burstLenLower)))
	localSettings.burstLenUpper = int64(math.Max(0, float64(*burstLenUpper)))
	localSettings.delayLenLower = int64(math.Max(0, math.Min(float64(*delayLenLower), float64(*delayLenUpper))))

	localSettings.delayLenUpper = int64(math.Max(0, math.Min(float64(*delayLenLower), float64(*delayLenUpper))))

	localSettings.maxClients = *maxClientsPtr

	fmt.Printf("The server is running on %s:%s \n", *address, *port)
	fmt.Printf("Unreliability parameters are: \n Burst %f \n Drop %f \n Flip %f, \n Delay %f \n The number of max clients are %d \n", localSettings.burst, localSettings.drop, localSettings.flip, localSettings.delay, localSettings.maxClients)

	rand.Seed(time.Now().Unix())

	lc := net.ListenConfig{
		Control: func(network, address string, c syscall.RawConn) error {
			return c.Control(func(fd uintptr) {
				// Set SO_REUSEADDR to allow immediate reuse of the port
				syscall.SetsockoptInt(int(fd), syscall.SOL_SOCKET, syscall.SO_REUSEADDR, 1)
			})
		},
	}

	pc, err := lc.ListenPacket(context.Background(), "udp", *address+":"+*port)
	if err != nil {
		log.Fatal(err)
	}
	defer pc.Close()

	output := BrokenMessageOutputStream{pc}

	buffer := make([]byte, 2048)
	for {
		n, addr, err := pc.ReadFrom(buffer)
		cb.Clean()
		message := string(buffer[:n])
		nli := strings.Index(message, "\n")
		if nli >= 0 {
			message = message[:nli]
			log.Println("FROM " + addr.String() + ": " + message)

			i := strings.Index(message, " ")
			header := message
			if i > 0 {
				header = message[:i]
			}
			var handler handleFunc
			switch header {
			case "HELLO-FROM":
				handler = handleHello
			case "SEND":
				handler = handleSend
			case "LIST":
				handler = handleWho
			case "GET":
				handler = handleGet
			case "SET":
				handler = handleSet
			case "RESET":
				handler = handleReset
			default:
				handler = handleBadHeader
			}
			handler(message, addr, output)
		}

		if err != nil {
			log.Fatal(err)
		}
	}
}

type handleFunc func(string, net.Addr, BrokenMessageOutputStream)

func handleBadHeader(_ string, addr net.Addr, output BrokenMessageOutputStream) {
	output.Send(addr, ReplyBadHdr)
}

func handleWho(message string, addr net.Addr, output BrokenMessageOutputStream) {
	if currentUserName, ok := cb.GetUser(addr); ok {
		if message == "LIST" {
			// Only send name of current user. To prevent spamming other users, with other protocols.
			output.Send(addr, "LIST-OK "+currentUserName+"\n")
		} else {
			output.Send(addr, ReplyBadBody)
		}
	}
}

func handleSend(message string, addr net.Addr, output BrokenMessageOutputStream) {
	if currentUserName, ok := cb.GetUser(addr); ok {
		if match := regexSend.FindStringSubmatch(message); match != nil {
			dst := match[3]
			msg := match[4]
			if recipient, ok := cb.GetAddress(dst); ok {
				dstAddr, _ := net.ResolveUDPAddr("udp", recipient)
				output.Send(dstAddr, "DELIVERY "+currentUserName+" "+msg+"\n")
				output.Send(addr, ReplySendOK)
			} else {
				output.Send(addr, ReplyUnknown)
			}
		} else {
			output.Send(addr, ReplyBadBody)
		}
	}
}

func handleHello(message string, addr net.Addr, output BrokenMessageOutputStream) {
	if match := regexName.FindStringSubmatch(message); match != nil { // New client
		if cb.IsFull() { // HELLO-FROM format is correct, but server busy
			output.Send(addr, ReplyBusy)
		} else { // HELLO-FROM format is correct. Enough space for new client
			name := match[3]
			if cb.IsKnown(name) { // But this username already exists
				if cb.nameToAddr[name] == addr.String(){ // check if username belongs to this address
					output.Send(addr, ReplyBadHdr)
				} else {
					output.Send(addr, ReplyInUse)
				}
			} else { // We don't know this user
				cb.Add(addr, name)
				output.Send(addr, "HELLO "+name+"\n")
			}
		}
	} else {
		output.Send(addr, ReplyBadBody)
	}
}

func handleGet(message string, addr net.Addr, output BrokenMessageOutputStream) {
	if _, ok := cb.GetUser(addr); ok {
		if match := regexGet.FindStringSubmatch(message); match != nil {
			var b strings.Builder
			b.WriteString(fmt.Sprintf("VALUE %s",match[3]))
			switch match[3] {
			case "DROP":
				b.WriteString(fmt.Sprintf("%f", localSettings.drop))
			case "FLIP":
				b.WriteString(fmt.Sprintf("%f", localSettings.flip))
			case "BURST":
				b.WriteString(fmt.Sprintf("%f", localSettings.burst))
			case "BURST-LEN":
				b.WriteString(fmt.Sprintf("%d %d", localSettings.burstLenLower, localSettings.burstLenUpper))
			case "DELAY":
				b.WriteString(fmt.Sprintf("%f", localSettings.delay))
			case "DELAY-LEN":
				b.WriteString(fmt.Sprintf("%d %d", localSettings.delayLenLower, localSettings.delayLenUpper))
			default:
				output.Send(addr, ReplyBadBody)
				return
			}
			b.WriteByte('\n')
			output.Send(addr, b.String())
		} else {
			output.Send(addr, ReplyBadBody)
		}
	}
}
func handleSet(message string, addr net.Addr, output BrokenMessageOutputStream) {
	success := false 
	if _, ok := cb.GetUser(addr); ok {
		if match := regexSet.FindStringSubmatch(message); match != nil {

			value, err := strconv.ParseFloat(match[4], 64)
			if err != nil {
				output.Send(addr, ReplyBadBody)
				return
			}

			// Handle SET requests one value
			switch match[3] {
			case "DROP":
				localSettings.drop = math.Max(0, math.Min(value, 1))
				success = true
			case "FLIP":
				localSettings.flip = math.Max(0, math.Min(value, 1))
				success = true
			case "BURST":
				localSettings.burst = math.Max(0, math.Min(value, 1))
				success = true
			case "DELAY":
				localSettings.delay = math.Max(0, math.Min(value, 1))
				success = true
			default:
				output.Send(addr, ReplyBadBody)
				return
			}
		} else if match := regexSetRange.FindStringSubmatch(message); match != nil {
			lower, err := strconv.ParseInt(match[4], 10, 64)
			if err != nil {
				output.Send(addr, ReplyBadBody)
				return
			}
			upper, err := strconv.ParseInt(match[5], 10, 64)
			if err != nil {
				output.Send(addr, ReplyBadBody)
				return
			}

			// Handle SET requests with range of values
			switch match[3] {
			case "BURST-LEN":
				localSettings.burstLenLower = int64(math.Max(0, float64(lower)))
				localSettings.burstLenUpper = int64(math.Max(0, float64(upper)))
				success = true
			case "DELAY-LEN":
				localSettings.delayLenLower = int64(math.Max(0, math.Min(float64(lower), float64(upper))))
				localSettings.delayLenUpper = int64(math.Max(0, math.Max(float64(lower), float64(upper))))
				success = true
			default:
				output.Send(addr, ReplyBadBody)
				return
			}
		}

		if success {
			output.Send(addr, ReplySetOK)
		} else {
			output.Send(addr, ReplyBadBody)
		}
	}
}
func handleReset(message string, addr net.Addr, output BrokenMessageOutputStream) {
	localSettings.drop = 0
	localSettings.flip = 0
	localSettings.burst = 0
	localSettings.delay = 0
	localSettings.burstLenLower = 3
	localSettings.burstLenUpper = 3
	localSettings.delayLenLower = 5
	localSettings.delayLenUpper = 5
	output.Send(addr, ReplySetOK)
}
